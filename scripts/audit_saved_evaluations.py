"""Verify completed local MASK/capability outputs and refresh metrics using saved calls."""
import collections,datetime,decimal,hashlib,json,os,re,shutil,subprocess
from pathlib import Path
from steering.official_mask import ROOT,RUN,complete_lines,load_official,classify_response
from steering.grade_pilot import CONDITIONS,pressure_unknown,refusal,save
from steering.sensitivity import compute as sensitivity
from steering.paired_analysis import compute as paired_analysis

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def key(row):return tuple(row[k] for k in ['config','task_id','condition','prompt_type'])
def latest_items(folder):return {(r['config'],r['task_id'],r['condition']):r for r in complete_lines(folder/'items.jsonl')}

def main():
    assert subprocess.run(['tmux','has-session','-t','=mask-expanded-score'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0,'Wait for the active scorer to finish'
    plan=json.loads((RUN/'mask_expanded_subset.json').read_text());locked=json.loads((RUN/'locked_settings.json').read_text());settings=digest(RUN/'locked_settings.json')
    assert digest(RUN/'fit.pt')==locked['fit_sha256']
    frozen=RUN/'pilot_before_expansion_frozen';frozen.mkdir(exist_ok=True)
    for name,expected in [('paired_summary.json',plan['pilot_summary_sha256']),('items.jsonl',plan['pilot_items_sha256'])]:
        destination=frozen/name
        if not destination.exists():
            assert digest(RUN/'judge_gptoss'/name)==expected
            shutil.copy2(RUN/'judge_gptoss'/name,destination)
        assert digest(destination)==expected
    for name in ['calls.jsonl','validation.json']:
        if not (frozen/name).exists():shutil.copy2(RUN/'judge_gptoss'/name,frozen/name)
    folders=[RUN/'judge_gptoss',RUN/'judge_gptoss_expanded']
    before={}
    for folder in folders:
        archive=folder/'before_metric_refresh';archive.mkdir(exist_ok=True)
        for name in ['items.jsonl','paired_summary.json']:
            if not (archive/name).exists():shutil.copy2(folder/name,archive/name)
        before[folder.name]={'calls_sha256':digest(folder/'calls.jsonl'),'honesty':{k:r['honesty'] for k,r in latest_items(folder).items()}}
        env=os.environ.copy();env['MASK_JUDGE_FOLDER']=str(folder);env['MASK_SUBSET_PATH']=str(RUN/('mask_subset.json' if folder.name=='judge_gptoss' else 'mask_expanded_subset.json'))
        subprocess.run(['bash','scripts/grade_mask_pilot.sh','--backend','local'],env=env,check=True)
        assert digest(folder/'calls.jsonl')==before[folder.name]['calls_sha256'],'Metric refresh must not make new judge calls'
        assert {k:r['honesty'] for k,r in latest_items(folder).items()}==before[folder.name]['honesty'],'Primary honesty must remain unchanged'
    from datasets import load_from_disk
    sources={}
    for config in sorted({i['config'] for i in plan['items']}):
        sources[config]={str(r['task_id']):r for r in load_from_disk(str(ROOT/'data/cais__MASK'/config/'test'))}
    expected=set()
    for item in plan['items']:
        row=sources[item['config']][item['task_id']]
        types=['pressured']+['belief_'+str(i) for i in [1,2,3] if row.get('belief_elicit_'+str(i))]
        expected.update((item['config'],item['task_id'],c,t) for c in CONDITIONS for t in types)
    generations={};duplicates=0
    for path in RUN.glob('mask_generations*.jsonl'):
        for row in complete_lines(path):
            k=key(row)
            if k in generations:
                duplicates+=1;previous=generations[k]
                assert previous['messages']==row['messages'] and previous['result']['token_ids']==row['result']['token_ids'],'Conflicting generation duplicate'
            assert row['settings_sha256']==settings and len(row['result']['token_ids'])<=256
            generations[k]=row
    assert set(generations)==expected and len(expected)==3800
    prompt_groups=collections.defaultdict(set)
    for k,row in generations.items():prompt_groups[k[0],k[1],k[3]].add(json.dumps(row['messages'],sort_keys=True))
    assert all(len(values)==1 for values in prompt_groups.values())
    official=load_official();folder=RUN/'judge_gptoss_expanded'
    calls={r['request_id']:r for r in complete_lines(folder/'calls.jsonl')}
    for request_id,call in calls.items():
        payload=call['request'];assert payload['model']=='openai/gpt-oss-20b' and payload['temperature']==0 and payload['seed']==42 and payload['max_tokens']==4096 and payload['reasoning_effort']=='low'
        assert 'condition' not in payload and all('condition' not in m for m in payload['messages'])
        binding=hashlib.sha256(json.dumps({'payload':payload,'judge_revision':call['judge_revision']},sort_keys=True).encode()).hexdigest();assert binding==request_id
        assert call['judge_revision']['revision']=='6cee5e81ee83917806bbde320786a8fb61efebee'
        status,parsed,content=classify_response(call['response'],call['numeric'],official)
        assert status==call['status']=='ok'
        assert (list(parsed) if call['numeric'] else parsed)==call['parsed']
    items=latest_items(folder);item_keys={(i['config'],i['task_id'],c) for i in plan['items'] for c in CONDITIONS}
    assert set(items)==item_keys and len(items)==1200
    for k,item in items.items():
        config,task,condition=k;row=sources[config][task];scoring=item['scoring_inputs'];numeric=config=='statistics'
        assert item['status']=='complete' and not item['judge_failures'] and item['settings_sha256']==settings
        assert scoring['ground_truth_extracted']==row['formatted_ground_truth']
        assert all(request in calls for request in item['request_ids'])
        pressure=generations[config,task,condition,'pressured']
        request=calls[item['request_ids'][0]]['request']['messages'][-1]['content']
        assert pressure['result']['text'].strip() in request,'Pressure judgment bound to wrong generation'
        assert item['target_response_truncated']==pressure['result']['hit_token_limit']
        assert item['target_response_refusal_regex']==refusal(pressure['result']['text'])
        belief_columns=[col for col in scoring if col.startswith('eval_belief_elicit_')]
        if belief_columns:
            value=official['aggregate_eval_beliefs_statistics' if numeric else 'aggregate_eval_beliefs'](scoring,belief_columns)
            if numeric:assert set(official['parse_tuple_string'](value))==set(official['parse_tuple_string'](scoring['eval_belief']))
            else:assert value==scoring['eval_belief']
        honesty=int(official['aggregate_eval_honesty_statistics' if numeric else 'aggregate_eval_honesty'](scoring,['pressure'],'eval_belief'))
        assert honesty==item['honesty']
        assert item['pressure_abstention_or_unknown']==pressure_unknown(scoring['pressure'],numeric,official)
    summary=json.loads((folder/'paired_summary.json').read_text());assert summary['paired_complete_items']==summary['target_items']==240
    for c in CONDITIONS:
        values=[r for k,r in items.items() if k[2]==c];counts=collections.Counter(r['honesty'] for r in values);s=summary['conditions'][c]
        assert s['paired_denominator']==s['complete_items']==240 and s['technical_failures']==0
        assert (s['honest'],s['dishonest'],s['undetermined'])==(counts[1],counts[-1],counts[0])
    secondary=sensitivity(folder);assert secondary['conditions']['baseline']['changed_from_primary']==0
    paired=paired_analysis(folder)
    capability={};multiple_markers=[]
    dataset_specs={'mmlu':('cais__mmlu/all/test',30),'gsm8k':('openai__gsm8k/main/test',10)}
    datasets={b:load_from_disk(str(ROOT/'data'/relative)) for b,(relative,n) in dataset_specs.items()}
    selected={b:set(sorted(range(len(datasets[b])),key=lambda i:hashlib.sha256((b+str(i)).encode()).hexdigest())[:n]) for b,(relative,n) in dataset_specs.items()}
    for c in CONDITIONS:
        rows=complete_lines(RUN/f'capability_{c}.jsonl');assert len(rows)==40
        assert {(r['benchmark'],r['index']) for r in rows}=={(b,i) for b in selected for i in selected[b]}
        for r in rows:
            b=r['benchmark'];gold=datasets[b][r['index']];assert r['settings_sha256']==settings
            expected=chr(65+gold['answer']) if b=='mmlu' else gold['answer'].split('####')[-1].strip().replace(',','')
            assert r['expected']==expected
            if b=='mmlu':
                match=re.search(r'\b([ABCD])\b',r['result']['text']);prediction=match.group(1) if match else None;correct=prediction==expected
            else:
                matches=re.findall(r'####\s*([-+]?\d[\d,]*(?:\.\d+)?)',r['result']['text']);prediction=matches[0].replace(',','') if matches else None
                if len(matches)>1:multiple_markers.append([c,r['index'],matches]);assert matches[0]==matches[-1],'Ambiguous multiple answer markers'
                correct=prediction is not None and decimal.Decimal(prediction)==decimal.Decimal(expected)
            assert prediction==r['prediction'] and correct==r['correct']
        capability[c]={b:{'n':sum(r['benchmark']==b for r in rows),'correct':sum(r['correct'] for r in rows if r['benchmark']==b)} for b in datasets}
    result={'status':'passed','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'settings_sha256':settings,'fit_sha256':digest(RUN/'fit.pt'),'paired_mask_items':240,'condition_item_judgments':1200,'unique_generations':len(generations),'identical_duplicate_generations':duplicates,'identical_prompt_groups':len(prompt_groups),'generation_counts':dict(collections.Counter(k[2] for k in generations)),'judge_calls_verified':len(calls),'primary_honesty_recomputed':len(items),'cache_only_refresh':True,'original_pilot_hashes_preserved':str(frozen),'capability_gold_verified':200,'capability':capability,'multiple_gsm_answer_markers':multiple_markers,'rank2_vs_pooled':paired['rank2_vs_pooled'],'normalization_updates':{f.name:len(complete_lines(f/'items.jsonl'))-len(complete_lines(f/'before_metric_refresh/items.jsonl')) for f in folders}}
    save(RUN/'overnight_saved_output_audit.json',result);print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
