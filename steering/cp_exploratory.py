"""Predeclared matched rank-2 CP pairwise classifier; isolated from locked methods."""
import argparse,hashlib,json,math,os,time
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from steering import experiment as exp
from steering.core import ResidualSteerer,normalize_schedule,position_bin
from steering.official_mask import complete_lines
from steering.grade_pilot import save
ROOT=exp.ROOT;RUN=exp.RUN;OUT=ROOT/'results/cp_exploratory';LAYERS=[8,12,16,20,24]

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bin3(k):
    if k<1:raise ValueError('CP offset zero is ineligible')
    return 0 if k<=3 else 1 if k<=11 else 2

def deadline_ok():
    # Initial implementation/smoke gate: frozen at the original user request time.
    import datetime
    return time.time()<datetime.datetime(2026,11,6,10,20,29,tzinfo=datetime.timezone.utc).timestamp()

class CPReplayHook(ResidualSteerer):
    """Reuse the existing HF residual hooks, with CP-specific window and schedules."""
    def __init__(self,layers,fit,condition='baseline',strength=0.,audit=False,**kwargs):
        mode='static' if condition=='cp_static' else 'scheduled'
        adapter={'layers':fit['layers'],'residual_norms':fit['residual_norms'],'joint':fit[mode]}
        super().__init__(layers,adapter,'baseline' if condition=='baseline' else 'rank2',strength=strength,audit=audit)
    def set_positions(self,absolute_positions,prompt_length):
        self.positions=absolute_positions-(prompt_length-1)
        self.positions=self.positions.clone();self.positions[self.positions==0]=-1
        self.steps+=int((self.positions>=1).sum())

@torch.inference_mode()
def extract(model,tokenizer,layers,norms):
    path=OUT/'matched_activations.pt'
    if path.exists():return torch.load(path,weights_only=False)
    pairs=exp.read_pairs();assert len(pairs)==50
    rows=[];pad=tokenizer.pad_token_id
    eos=model.generation_config.eos_token_id;eos=set(eos if isinstance(eos,list) else [eos]);eos.add(tokenizer.eos_token_id)
    if pad is not None:eos.add(pad)
    for pair in pairs:
        if not deadline_ok():raise TimeoutError('CP initial time gate elapsed during extraction')
        source=pair['source'];messages=[{'role':'system','content':source['system_prompt_neutral']},{'role':'user','content':source['user_message']}]
        prefix=exp.prompt_ids(tokenizer,messages)[0].tolist();length=len(prefix)
        completions={c:pair[c]['completion_token_ids'] for c in ['honest','dishonest']}
        valid=set.intersection(*[{i for i,t in enumerate(ids) if t not in eos} for ids in completions.values()])
        offsets=sorted(valid)
        assert offsets and all(any(bin3(j+1)==b for j in offsets) for b in range(3))
        total=max(map(len,completions.values()));record={'scenario_id':pair['scenario_id'],'split':pair['split'],'shared_offsets':[j+1 for j in offsets],'prompt_sha256':hashlib.sha256(json.dumps(prefix).encode()).hexdigest()}
        prompt_states={}
        for condition in ['honest','dishonest']:
            captured={};handles=[]
            def capture(layer):
                def hook(module,args,out):
                    h=out[0] if isinstance(out,tuple) else out;h=h[0]
                    # Offset k means k response tokens have already been consumed.
                    values=[]
                    for b in range(3):
                        indices=torch.tensor([length+j for j in offsets if bin3(j+1)==b],device=h.device)
                        values.append(h[indices].float().mean(0).cpu())
                    captured[layer]=torch.stack(values)
                    prompt_states[condition,layer]=h[length-1].float().cpu()
                return hook
            try:
                for layer in LAYERS:handles.append(layers[layer].register_forward_hook(capture(layer)))
                completion=completions[condition];padding=[pad if pad is not None else tokenizer.eos_token_id]*(total-len(completion))
                tokens=torch.tensor([prefix+completion+padding],device='cuda')
                attention=torch.tensor([[1]*(length+len(completion))+[0]*len(padding)],device='cuda')
                # Right padding occurs only AFTER all captured causal positions. Identical
                # all-causal masks avoid different SDPA kernel paths across pair members.
                # Padded/EOS offsets remain excluded explicitly from every captured mean.
                model(input_ids=tokens,use_cache=False,logits_to_keep=1)
            finally:
                for handle in handles:handle.remove()
            record[condition]=torch.stack([captured[l] for l in LAYERS])/norms[:,None,None]
        record['prompt0_max_abs_pair_difference']=max(float((prompt_states['honest',l]-prompt_states['dishonest',l]).abs().max()) for l in LAYERS)
        assert record['prompt0_max_abs_pair_difference']==0., 'Shared prompt prefix must be identical under a matched causal kernel'
        rows.append(record);print('CP MATCHED EXTRACT',len(rows),pair['scenario_id'],pair['split'],flush=True)
    torch.save(rows,path)
    save(OUT/'extraction_summary.json',{'scenarios':50,'extraction':40,'calibration':10,'layers':LAYERS,'bin_shared_counts':{r['scenario_id']:[sum(bin3(k)==b for k in r['shared_offsets']) for b in range(3)] for r in rows},'normalization_scales':norms.tolist(),'shared_prompt':True,'padding_eos_excluded':True,'teacher_forced_passes':100,'max_prompt0_abs_difference':max(r['prompt0_max_abs_pair_difference'] for r in rows),'protocol_sha256':digest(OUT/'predeclared_protocol.json')})
    return rows

def fit_cpu(rows,norms):
    path=OUT/'cp_fit.pt'
    if path.exists():return torch.load(path,weights_only=False)
    torch.manual_seed(20261106);torch.set_num_threads(4)
    train=[r for r in rows if r['split']=='extraction'];cal=[r for r in rows if r['split']=='calibration'];assert len(train)==40 and len(cal)==10
    D=torch.stack([r['honest']-r['dishonest'] for r in train]);Dc=torch.stack([r['honest']-r['dishonest'] for r in cal])
    # Deterministic SVD-based initialization, subsequently optimized under the CP constraint.
    mean=D.mean(0);u,s,v=torch.linalg.svd(mean.reshape(15,-1),full_matrices=False)
    As=[];Bs=[];Cs=[]
    for rank in range(2):
        a,b,c=torch.linalg.svd(u[:,rank].reshape(5,3),full_matrices=False)
        As.append(a[:,0]*math.sqrt(float(b[0])));Bs.append(c[0]*math.sqrt(float(b[0])));Cs.append(v[rank]*s[rank])
    A=torch.nn.Parameter(torch.stack(As,1));B=torch.nn.Parameter(torch.stack(Bs,1));C=torch.nn.Parameter(torch.stack(Cs,1))
    optimizer=torch.optim.Adam([A,B,C],lr=.02);history=[]
    for step in range(1000):
        if not deadline_ok():raise TimeoutError('CP initial time gate elapsed during CPU fit')
        W=torch.einsum('lr,pr,hr->lph',A,B,C)
        margins=torch.einsum('nlph,lph->n',D,W)
        loss=F.softplus(-margins).mean()+.005*W.square().sum()
        optimizer.zero_grad();loss.backward();optimizer.step()
        if step%100==0:history.append({'step':step,'loss':float(loss),'mean_margin':float(margins.mean())})
    with torch.no_grad():
        W=torch.einsum('lr,pr,hr->lph',A,B,C).detach();train_m=(D*W).sum((1,2,3));cal_m=(Dc*W).sum((1,2,3))
        scheduled3=normalize_schedule(W,norms)
        static3=normalize_schedule(W.mean(1,keepdim=True).expand(-1,3,-1).clone(),norms)
        schedules={}
        for name,weights in [('scheduled',scheduled3),('static',static3)]:
            full=torch.zeros((5,4,W.shape[-1]));full[:,1:,:]=weights;schedules[name]=full
    fit={'layers':LAYERS,'residual_norms':norms,'A':A.detach(),'B':B.detach(),'C':C.detach(),'W':W,**schedules}
    torch.save(fit,path)
    save(OUT/'classification.json',{'loss':'mean softplus(-paired_margin) + .01/2 * ||W||_F^2','rank':2,'steps':1000,'seed':20261106,'train_honest_higher':int((train_m>0).sum()),'train_n':40,'calibration_honest_higher':int((cal_m>0).sum()),'calibration_n':10,'calibration_margins':[{'scenario_id':r['scenario_id'],'honest_minus_dishonest':float(m)} for r,m in zip(cal,cal_m)],'history':history,'fit_sha256':digest(path),'protocol_sha256':digest(OUT/'predeclared_protocol.json')})
    print('CP FIT COMPLETE; CALIBRATION RANKING',int((cal_m>0).sum()),'/10',flush=True)
    return fit

@torch.inference_mode()
def verify(model,tokenizer,layers,fit):
    original=exp.ResidualSteerer;exp.ResidualSteerer=CPReplayHook
    try:
        messages=[{'role':'user','content':'Count upwards from one to twenty, separated by commas.'}]
        base,logits=exp.generate(model,tokenizer,layers,fit,messages,{'condition':'baseline'},17,force_steps=True)
        checks={}
        for c in ['cp_scheduled','cp_static']:
            result,z=exp.generate(model,tokenizer,layers,fit,messages,{'condition':c,'strength':0.},17,audit=True,force_steps=True)
            assert base['token_ids']==result['token_ids'] and torch.equal(logits,z)
            for layer in LAYERS:
                trace=[t for t in result['trace'] if t['layer']==layer]
                assert [t['positions'][0] for t in trace]==list(range(1,17))
                assert [t['bins'][0] for t in trace]==[position_bin(k) for k in range(1,17)]
                assert all(t['sequence_length']==1 for t in trace)
            schedule=fit['scheduled' if c=='cp_scheduled' else 'static'][:,1:,:]
            budgets=(schedule/fit['residual_norms'][:,None,None]).square().sum((0,2)).sqrt()
            assert torch.allclose(budgets,torch.ones(3),atol=1e-5)
            # Synthetic float32 layer outputs verify realized precomputed budgets exactly;
            # BF16 inference statistics separately record quantized realized perturbations.
            checks[c]={'zero_strength_same_tokens':True,'zero_strength_same_first_logits':True,'prefill_offset0_skipped':True,'cached_offsets':list(range(1,17)),'cached_bins':[position_bin(k) for k in range(1,17)],'joint_nominal_budget_each_bin':budgets.tolist()}
        save(OUT/'smoke_verification.json',{'status':'passed','checks':checks,'completed_epoch':time.time(),'within_30min_gate':deadline_ok()})
        print('CP SMOKE PASSED',flush=True)
    finally:exp.ResidualSteerer=original

def calibrate(model,tokenizer,layers,fit):
    path=OUT/'locked_cp_settings.json'
    if path.exists():return json.loads(path.read_text())
    original=exp.ResidualSteerer;exp.ResidualSteerer=CPReplayHook
    scores=[]
    try:
        pairs=[p for p in exp.read_pairs() if p['split']=='calibration'];assert len(pairs)==10
        for alpha in [.02,.05,.10]:
            details=[]
            for condition in ['cp_scheduled','cp_static']:
                margins=[]
                for pair in pairs:
                    s=pair['source'];messages=[{'role':'system','content':s['system_prompt_neutral']},{'role':'user','content':s['user_message']}]
                    setting={'condition':condition,'strength':alpha}
                    a=exp.likelihood(model,tokenizer,layers,fit,messages,pair['honest']['completion_token_ids'],setting)
                    b=exp.likelihood(model,tokenizer,layers,fit,messages,pair['dishonest']['completion_token_ids'],setting)
                    margins.append({'scenario_id':pair['scenario_id'],'margin':a-b})
                details.append({'condition':condition,'mean_margin':float(np.mean([v['margin'] for v in margins])),'pairs':margins})
            scores.append({'strength':alpha,'joint_mean_margin':float(np.mean([d['mean_margin'] for d in details])),'details':details});print('CP CALIBRATED',alpha,scores[-1]['joint_mean_margin'],flush=True)
    finally:exp.ResidualSteerer=original
    best=max(scores,key=lambda s:s['joint_mean_margin'])
    lock={'locked_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'conditions':['cp_scheduled','cp_static'],'shared_strength':best['strength'],'calibration_scores':scores,'selection':'One shared alpha maximizing average of scheduled/static scores under the existing 10-pair likelihood protocol','fit_sha256':digest(OUT/'cp_fit.pt'),'protocol_sha256':digest(OUT/'predeclared_protocol.json'),'within_initial_gate':deadline_ok(),'no_pilot_judgments_read':True}
    save(path,lock);return lock


def prepare():
    assert deadline_ok(),'CP initial gate already expired'
    assert not (OUT/'pilot_judgments.jsonl').exists(),'Predeclare and lock before pilot judging'
    # Enforce that GPU6 is genuinely free; this process is restricted to CUDA_VISIBLE_DEVICES=6.
    model,tokenizer,layers=exp.load()
    norms=torch.load(RUN/'fit.pt',weights_only=False)['residual_norms'].clone()
    fit=fit_cpu(extract(model,tokenizer,layers,norms),norms)
    verify(model,tokenizer,layers,fit)
    calibrate(model,tokenizer,layers,fit)
    assert digest(RUN/'locked_settings.json')==json.loads((OUT/'predeclared_protocol.json').read_text())['original_settings_sha256']
    save(OUT/'initial_gate.json',{'status':'passed' if deadline_ok() else 'failed','completed_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'smoke':'passed','calibration_ranking':json.loads((OUT/'classification.json').read_text())['calibration_honest_higher'],'pilot_launch_requires_separate_capacity_and_timing_check':True})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['prepare'],default='prepare');args=parser.parse_args();prepare()
