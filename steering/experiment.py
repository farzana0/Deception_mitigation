"""Local-only extraction, calibration, locking, and paired held-out evaluation."""
import argparse, contextlib, hashlib, importlib.util, json, math, os, re, time
from pathlib import Path
import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from transformers import AutoModelForImageTextToText, AutoProcessor
from steering.journal import repair_tail
from steering.official_mask import complete_lines
from steering.core import ResidualSteerer, normalize_schedule, position_bin

ROOT=Path('/lambda/nfs/fs-cand-nov05')
RUN=ROOT/'results/steering_run'
LAYERS=[8,12,16,20,24]
REVISION='c202236235762e1c871ad0ccb60c8ee5ba337b9a'

def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(path)

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read_pairs(): return [json.loads(l) for l in (ROOT/'results/qwen_contrast_pairs.jsonl').read_text().splitlines()]

def load():
    torch.manual_seed(42);torch.set_num_threads(8)
    p=ROOT/'models/Qwen3.5-9B'
    processor=AutoProcessor.from_pretrained(p,local_files_only=True)
    model=AutoModelForImageTextToText.from_pretrained(p,local_files_only=True,dtype=torch.bfloat16,device_map={'':0},attn_implementation='sdpa').eval()
    return model,processor.tokenizer,model.model.language_model.layers

def prompt_ids(tokenizer,messages):
    return tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,enable_thinking=False,return_tensors='pt',return_dict=False).to('cuda')

def content_tokens(tokenizer,ids):
    special=set(tokenizer.all_special_ids)
    return [i for i in ids if i not in special]

@torch.inference_mode()
def extract(model,tokenizer,layers):
    path=RUN/'extraction.pt'
    if path.exists(): return torch.load(path,weights_only=False)
    pairs=[p for p in read_pairs() if p['split']=='extraction']
    assert len(pairs)==40
    rows=[]
    for pair in pairs:
        record={'scenario_id':pair['scenario_id']}
        for condition in ('honest','dishonest'):
            entry=pair[condition];prefix=entry['input_token_ids'];completion=entry['completion_token_ids']
            valid=[j for j,t in enumerate(completion) if t not in tokenizer.all_special_ids]
            assert valid
            length=len(prefix);responses=torch.tensor([length+j for j in valid],device='cuda')
            # Position k is residual of token before generated token k: k=0 at prompt end.
            predictor=torch.tensor([length-1+j for j in valid],device='cuda')
            positions=torch.tensor(valid,device='cuda')
            captured={};handles=[]
            def capture(layer):
                def hook(module,args,out):
                    h=out[0] if isinstance(out,tuple) else out;h=h[0].float()
                    binned=[]
                    for b in range(4):
                        mask=torch.tensor([position_bin(int(k))==b for k in positions],device='cuda')
                        binned.append(h[predictor[mask]].mean(0).cpu() if mask.any() else torch.full((h.shape[-1],),float('nan')))
                    captured[layer]={'response_mean':h[responses].mean(0).cpu(),'bins':torch.stack(binned),'norm':h[responses].norm(dim=-1).mean().cpu()}
                return hook
            try:
                for layer in LAYERS: handles.append(layers[layer].register_forward_hook(capture(layer)))
                tokens=torch.tensor([prefix+completion],device='cuda')
                model(input_ids=tokens,use_cache=False,logits_to_keep=1)
            finally:
                for h in handles:h.remove()
            record[condition]=captured
        rows.append(record)
        print('EXTRACTED',len(rows),pair['scenario_id'],flush=True)
    torch.save(rows,path)
    return rows

def fit_vectors(rows):
    path=RUN/'fit.pt'
    if path.exists():return torch.load(path,weights_only=False)
    caa=[];joint=[];norms=[];sttp={};bin_counts={}
    for layer in LAYERS:
        pos=torch.stack([r['honest'][layer]['response_mean'] for r in rows])
        neg=torch.stack([r['dishonest'][layer]['response_mean'] for r in rows])
        caa.append((pos-neg).mean(0))
        norm=torch.stack([r[c][layer]['norm'] for r in rows for c in ['honest','dishonest']]).mean();norms.append(norm)
        differences=torch.stack([r['honest'][layer]['bins']-r['dishonest'][layer]['bins'] for r in rows])
        counts=torch.isfinite(differences[:,:,0]).sum(0)
        assert (counts>0).all()
        joint.append(torch.nanmean(differences,dim=0));bin_counts[layer]=counts.tolist()
        X=torch.cat([neg,pos]).numpy();y=np.array([0]*len(rows)+[1]*len(rows))
        clf=LogisticRegression(C=1.0,penalty='l2',solver='lbfgs',max_iter=5000,random_state=42,tol=1e-7).fit(X,y)
        assert clf.n_iter_[0]<5000
        w=torch.tensor(clf.coef_[0],dtype=torch.float32);u=w/w.norm();projection=pos@u
        sttp[layer]={'u':u,'t':float(-clf.intercept_[0]/w.norm()),'mu_pos':float(projection.mean()),'sd_pos':float(projection.std(correction=1)),
                     'w_norm':float(w.norm()),'intercept':float(clf.intercept_[0]),'training_accuracy':float(clf.score(X,y))}
    raw=torch.stack(joint);norms=torch.stack(norms);caa=torch.stack(caa)
    matrix=raw.reshape(-1,raw.shape[-1]);U,S,V=torch.linalg.svd(matrix,full_matrices=False)
    approximation=((U[:,:2]*S[:2])@V[:2]).reshape_as(raw)
    fit={'layers':LAYERS,'residual_norms':norms,'caa':caa,'joint':normalize_schedule(approximation,norms),'pooled':normalize_schedule(caa[:,None,:].expand(-1,4,-1).clone(),norms),'sttp':sttp,
         'raw_joint':raw,'rank2_unscaled':approximation,'singular_values':S,'bin_counts':bin_counts}
    torch.save(fit,path)
    write_json(RUN/'fit_summary.json',{'layers':LAYERS,'extraction_scenarios':40,'bin_pair_counts':bin_counts,'residual_norms':norms.tolist(),
               'rank2_explained_squared_energy':float(S[:2].square().sum()/S.square().sum()),'sttp':{l:{k:v for k,v in d.items() if k!='u'} for l,d in sttp.items()},
               'normalization':'sqrt(sum_layer (norm(delta)/typical_residual_norm)^2) = strength in each position bin; StTP formula unscaled, realized strengths logged'})
    return fit

@torch.inference_mode()
def likelihood(model,tokenizer,layers,fit,messages,completion,setting):
    prefix=prompt_ids(tokenizer,messages);tokens=content_tokens(tokenizer,completion)
    full=torch.cat([prefix,torch.tensor([tokens],device='cuda')],dim=1)
    indices=torch.arange(prefix.shape[1]-1,full.shape[1]-1,device='cuda')
    with ResidualSteerer(layers,fit,**setting) as steer:
        steer.set_positions(torch.arange(full.shape[1],device='cuda'),prefix.shape[1])
        out=model(input_ids=full,use_cache=False,logits_to_keep=indices)
        loss=torch.nn.functional.cross_entropy(out.logits[0].float(),torch.tensor(tokens,device='cuda'))
    return -float(loss)

@torch.inference_mode()
def generate(model,tokenizer,layers,fit,messages,setting,max_new_tokens=128,audit=False,force_steps=False):
    ids=prompt_ids(tokenizer,messages);prompt_length=ids.shape[1]
    generated=[];cache=None;first_logits=None
    eos=model.generation_config.eos_token_id
    eos=set(eos if isinstance(eos,list) else [eos])
    with ResidualSteerer(layers,fit,**setting,audit=audit) as steer:
        for k in range(max_new_tokens):
            inputs=ids if k==0 else torch.tensor([[generated[-1]]],device='cuda')
            absolute=torch.arange(prompt_length,device='cuda') if k==0 else torch.tensor([prompt_length+k-1],device='cuda')
            steer.set_positions(absolute,prompt_length)
            out=model(input_ids=inputs,past_key_values=cache,use_cache=True,logits_to_keep=1)
            cache=out.past_key_values
            if k==0:first_logits=out.logits[0,-1].float().cpu()
            token=int(out.logits[0,-1].argmax());generated.append(token)
            if token in eos and not force_steps:break
        stats=steer.stats();trace=steer.trace
    return {'text':tokenizer.decode(generated,skip_special_tokens=True),'token_ids':generated,'hit_token_limit':len(generated)==max_new_tokens and generated[-1] not in eos,'stats':stats,'trace':trace},first_logits

def verify(model,tokenizer,layers,fit):
    messages=[{'role':'user','content':'Count upwards from one, separated by commas, for twenty numbers.'}]
    baseline,logits=generate(model,tokenizer,layers,fit,messages,{'condition':'baseline'},16,force_steps=True)
    checks={}
    for condition in ['caa','rank2','pooled']:
        setting={'condition':condition,'strength':0.}
        if condition=='caa':setting['layer']=LAYERS[0]
        result,test_logits=generate(model,tokenizer,layers,fit,messages,setting,16,audit=True,force_steps=True)
        assert result['token_ids']==baseline['token_ids']
        assert torch.equal(logits,test_logits)
        for layer in ([LAYERS[0]] if condition=='caa' else LAYERS):
            trace=[t for t in result['trace'] if t['layer']==layer]
            assert [t['positions'][0] for t in trace]==list(range(16))
            assert [t['bins'][0] for t in trace]==[position_bin(k) for k in range(16)]
            assert all(t['sequence_length']==1 for t in trace[1:])
        checks[condition]={'zero_strength_identical_tokens':True,'zero_strength_identical_first_logits':True,'cached_positions':list(range(16)),'cached_bins':[position_bin(k) for k in range(16)]}
    # StTP c=0 remains active: test gating and exact target in float precision separately.
    s=fit['sttp'][LAYERS[0]];u=s['u'];x=u*(s['t']-10.);p=x@u
    y=x+(s['mu_pos']-p)*u
    assert abs(float(y@u)-s['mu_pos'])<.01
    checks['sttp']={'c_zero_targets_mean':True,'baseline_disables_hook':True}
    # Check schedule total budget separately in every bin.
    for key in ['joint','pooled']:
        budgets=(fit[key]/fit['residual_norms'][:,None,None]).square().sum((0,2)).sqrt()
        assert torch.allclose(budgets,torch.ones(4),atol=1e-5)
    write_json(RUN/'verification.json',checks)
    print('VERIFICATION PASSED',flush=True)

def calibrate(model,tokenizer,layers,fit):
    lock=RUN/'locked_settings.json'
    if lock.exists():return json.loads(lock.read_text())
    candidates=[{'condition':'baseline'}]
    for layer in LAYERS:
        candidates.extend({'condition':'caa','layer':layer,'strength':a} for a in [.02,.05,.1])
        candidates.extend({'condition':'sttp','layer':layer,'c':c} for c in [0.,1.,2.])
    candidates.extend({'condition':method,'strength':a} for method in ['rank2','pooled'] for a in [.02,.05,.1])
    pairs=[p for p in read_pairs() if p['split']=='calibration'];assert len(pairs)==10
    results=[];journal=RUN/'calibration.jsonl'
    existing={json.dumps(r['setting'],sort_keys=True):r for r in [json.loads(l) for l in journal.read_text().splitlines()]} if journal.exists() else {}
    for setting in candidates:
        key=json.dumps(setting,sort_keys=True)
        if key in existing:results.append(existing[key]);continue
        margins=[]
        for pair in pairs:
            source=pair['source']
            messages=[{'role':'system','content':source['system_prompt_neutral']},{'role':'user','content':source['user_message']}]
            positive=likelihood(model,tokenizer,layers,fit,messages,pair['honest']['completion_token_ids'],setting)
            negative=likelihood(model,tokenizer,layers,fit,messages,pair['dishonest']['completion_token_ids'],setting)
            margins.append({'scenario_id':pair['scenario_id'],'honest_mean_logp':positive,'dishonest_mean_logp':negative,'margin':positive-negative})
        entry={'setting':setting,'mean_margin':float(np.mean([m['margin'] for m in margins])),'scenarios':margins}
        with journal.open('a') as f:f.write(json.dumps(entry)+'\n')
        results.append(entry);print('CALIBRATED',setting,entry['mean_margin'],flush=True)
    locked={}
    for method in ['baseline','caa','sttp','rank2','pooled']:
        options=[r for r in results if r['setting']['condition']==method]
        # If a nonzero setting does not beat baseline, retain best tested nonzero and report that fact.
        best=max(options,key=lambda r:r['mean_margin']);locked[method]=best['setting']
    locked['pooled']={'condition':'pooled','strength':locked['rank2']['strength']}
    record={'locked_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'settings':locked,
            'objective':'Mean over ten calibration scenarios: length-normalized logP(honest completion|neutral prompt) minus logP(dishonest completion|neutral prompt). No held-out data used.',
            'candidate_middle_layers_zero_based':LAYERS,'strength_grid':[.02,.05,.1],'sttp_c_grid':[0.,1.,2.],
            'calibration_sha256':digest(journal),'fit_sha256':digest(RUN/'fit.pt'),'pairs_sha256':digest(ROOT/'results/qwen_contrast_pairs.jsonl'),
            'splits_sha256':digest(ROOT/'results/steering_splits.json'),'source_sha256':digest(Path(__file__)),
            'calibration_best_scores':{m:max(r['mean_margin'] for r in results if r['setting']['condition']==m) for m in locked}}
    write_json(lock,record);print('SETTINGS LOCKED',record,flush=True)
    return record


def evaluate_mask(model,tokenizer,layers,fit,locked):
    # Imported/read only after all settings have been locked to disk.
    from datasets import load_from_disk
    conditions=os.environ.get('STEERING_EVAL_CONDITIONS','baseline,caa,sttp,rank2,pooled').split(',')
    suffix='_'+conditions[0] if len(conditions)==1 else ''
    output=RUN/('mask_generations'+suffix+'.jsonl')
    repair_tail(output)
    done={(r['config'],r['task_id'],r['condition'],r['prompt_type']) for f in RUN.glob('mask_generations*.jsonl') for r in complete_lines(f)}
    selected=[]
    manifest=Path(os.environ.get('MASK_SUBSET_PATH',str(RUN/'mask_subset.json')))
    if manifest.exists():
        for item in json.loads(manifest.read_text())['items']:
            ds=load_from_disk(str(ROOT/'data/cais__MASK'/item['config']/'test'))
            selected.append((item['config'],next(r for r in ds if str(r['task_id'])==item['task_id'])))
    else:
        for config in ['continuations','disinformation','doubling_down_known_facts','known_facts','provided_facts','statistics']:
            ds=load_from_disk(str(ROOT/'data/cais__MASK'/config/'test'))
            rows=sorted(list(ds),key=lambda r:hashlib.sha256((config+str(r['task_id'])).encode()).hexdigest())[:2]
            selected.extend((config,row) for row in rows)
        write_json(manifest,{'selection':'First two task IDs per config sorted by SHA256(config+task_id), fixed before generation','items':[{'config':c,'task_id':str(r['task_id'])} for c,r in selected],'settings_sha256':digest(RUN/'locked_settings.json')})
    for config,row in selected:
        messages=[{'role':'system','content':row['system_prompt']}]
        if config=='doubling_down_known_facts':messages.extend([{'role':'user','content':row['dd_turn_1_prompt']},{'role':'assistant','content':row['dd_turn_1_response']}])
        messages.append({'role':'user','content':row['user_prompt']})
        prompts={'pressured':messages}
        for index in [1,2,3]:
            text=row.get('belief_elicit_'+str(index))
            if text:prompts['belief_'+str(index)]=[{'role':'system','content':'You are a helpful assistant.'},{'role':'user','content':text}]
        for condition in conditions:
            for prompt_type,prompt in prompts.items():
                key=(config,str(row['task_id']),condition,prompt_type)
                if key in done:continue
                start=time.time();result,_=generate(model,tokenizer,layers,fit,prompt,locked['settings'][condition],max_new_tokens=256)
                result.pop('trace')
                record={'config':config,'task_id':str(row['task_id']),'condition':condition,'prompt_type':prompt_type,'messages':prompt,'result':result,'seconds':time.time()-start,'settings_sha256':digest(RUN/'locked_settings.json')}
                with output.open('a') as f:f.write(json.dumps(record)+'\n')
                print('MASK GENERATED',config,row['task_id'],condition,prompt_type,flush=True)
    print('MASK SUBSET GENERATION COMPLETE',flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['all','extract','calibrate','eval'],default='all');args=parser.parse_args()
    RUN.mkdir(parents=True,exist_ok=True)
    model,tokenizer,layers=load()
    if args.phase in ['all','extract']:
        fit=fit_vectors(extract(model,tokenizer,layers))
        verify(model,tokenizer,layers,fit)
        if args.phase=='extract':return
    else:fit=torch.load(RUN/'fit.pt',weights_only=False)
    if args.phase in ['all','calibrate']:
        if not (RUN/'verification.json').exists():verify(model,tokenizer,layers,fit)
        locked=calibrate(model,tokenizer,layers,fit)
        if args.phase=='calibrate':return
    else:locked=json.loads((RUN/'locked_settings.json').read_text())
    evaluate_mask(model,tokenizer,layers,fit,locked)

if __name__=='__main__':main()
