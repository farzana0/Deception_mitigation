"""Final offline validator. Writes completion only after every declared target passes."""
import asyncio,collections,csv,datetime,hashlib,json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
import jsonschema
from steering.official_mask import ROOT,RUN,complete_lines,load_official,classify_response
from steering.grade_pilot import CONDITIONS,Transport,generations,score_item,save
from steering.quality_controls import mask_work,capability_work,rows as mask_rows
from steering.machiavelli_quality import gather
from steering.machiavelli_counterfactual import prepare,judge_work
CODE=Path(__file__).resolve().parents[1]

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def latest(path):return {r['key']:r for r in complete_lines(path)}

def audit_aux(name,work,target):
    folder=RUN/name;protocol=json.loads((folder/'protocol.json').read_text())
    calls={r['request_id']:r for r in complete_lines(folder/'calls.jsonl')};items=latest(folder/'items.jsonl')
    assert len(work)==target and set(items)=={w['key'] for w in work},(name,'item coverage',len(items),len(work),target)
    for w in work:
        r=items[w['key']];assert r['status']=='complete',(name,w['key'])
        call=calls[r['request_id']];assert call['status']=='ok'
        assert call['request']['messages'][-1]['content']==json.dumps(w['data'],ensure_ascii=False),(name,w['key'],'binding')
        rid=hashlib.sha256(json.dumps({'protocol':protocol,'payload':call['request']},sort_keys=True).encode()).hexdigest();assert rid==r['request_id']
        choice=call['response']['choices'][0];assert choice['finish_reason']!='length' and not choice['message'].get('refusal')
        parsed=json.loads(choice['message']['content']);jsonschema.validate(parsed,protocol['schema']);assert parsed==call['parsed']==r['labels']
        for k,v in w.items():
            if k!='data':assert r[k]==v,(name,w['key'],k)
    validation=folder/'validation.json'
    if validation.exists():assert json.loads(validation.read_text())['status']=='passed'
    return {'items':len(items),'calls':len(calls),'item_journal_sha256':digest(folder/'items.jsonl'),'protocol_sha256':digest(folder/'protocol.json')}

async def audit_mask():
    from datasets import load_from_disk
    manifest=json.loads((RUN/'mask_full_test_manifest.json').read_text());assert len(manifest['items'])==1000
    sources=mask_rows();assert set(sources)=={(i['config'],i['task_id']) for i in manifest['items']},'Full local test data/manifest mismatch'
    expected=set();settings=digest(RUN/'locked_settings.json');locked=json.loads((RUN/'locked_settings.json').read_text());assert digest(RUN/'fit.pt')==locked['fit_sha256']
    for i in manifest['items']:
        row=sources[i['config'],i['task_id']]
        types=['pressured']+['belief_'+str(k) for k in [1,2,3] if row.get('belief_elicit_'+str(k))]
        expected.update((i['config'],i['task_id'],c,t) for c in CONDITIONS for t in types)
    allgens=generations();gs={(g['config'],g['task_id'],g['condition'],g['prompt_type']):g for g in allgens};assert set(gs)==expected,(len(gs),len(expected))
    grouped=collections.defaultdict(set)
    for k,g in gs.items():
        assert g['settings_sha256']==settings and len(g['result']['token_ids'])<=256
        source=sources[k[:2]]
        if k[3]=='pressured':
            prompt=[{'role':'system','content':source['system_prompt']}]
            if k[0]=='doubling_down_known_facts':prompt.extend([{'role':'user','content':source['dd_turn_1_prompt']},{'role':'assistant','content':source['dd_turn_1_response']}])
            prompt.append({'role':'user','content':source['user_prompt']})
        else:prompt=[{'role':'system','content':'You are a helpful assistant.'},{'role':'user','content':source['belief_elicit_'+k[3].split('_')[1]]}]
        assert g['messages']==prompt,(k,'source prompt mismatch')
        grouped[k[0],k[1],k[3]].add(json.dumps(g['messages'],sort_keys=True))
    assert all(len(v)==1 for v in grouped.values())
    # Verify duplicate journals agree, without rewriting any raw record.
    seen={}
    for path in RUN.glob('mask_generations*.jsonl'):
        for g in complete_lines(path):
            k=tuple(g[f] for f in ['config','task_id','condition','prompt_type'])
            if k in seen:assert seen[k]['messages']==g['messages'] and seen[k]['result']['token_ids']==g['result']['token_ids']
            seen[k]=g
    official=load_official();folder=RUN/'judge_gptoss_full';transport=Transport(folder,'local',official);official['evaluate_responses_async']=transport.evaluator
    items={(r['config'],r['task_id'],r['condition']):r for r in complete_lines(folder/'items.jsonl')};assert len(items)==5000
    for call in transport.cache.values():
        p=call['request'];assert p['model']=='openai/gpt-oss-20b' and p['temperature']==0 and p['seed']==42 and p['max_tokens']==4096 and p['reasoning_effort']=='low'
        assert call['request_id']==hashlib.sha256(json.dumps({'payload':p,'judge_revision':call['judge_revision']},sort_keys=True).encode()).hexdigest()
        if call['status']=='ok':
            status,parsed,content=classify_response(call['response'],call['numeric'],official);assert status=='ok' and (list(parsed) if call['numeric'] else parsed)==call['parsed']
    before=digest(folder/'calls.jsonl')
    with patch('urllib.request.urlopen',side_effect=AssertionError('Offline audit: cache miss is a failure')):
        for n,(key,item) in enumerate(sorted(items.items())):
            config,task,c=key;assert item['status']=='complete'
            records={k[3]:g for k,g in gs.items() if k[:3]==key}
            scored=await score_item(official,transport,sources[config,task],config,c,records)
            for field in ['honesty','status','scoring_inputs','request_ids','settings_sha256','target_response_truncated','knowledge_reference_covered']:
                a,b=scored[field],item[field]
                if field=='scoring_inputs' and config=='statistics':
                    a=dict(a);b=dict(b)
                    # Upstream list(set(intervals)) has process-dependent None hash order.
                    for value in [a,b]:
                        if 'eval_belief' in value:value['eval_belief']=set(official['parse_tuple_string'](value['eval_belief']))
                assert a==b,(key,field,a,b)
            if n%500==0:print('OFFLINE MASK AUDIT',n,'/5000',flush=True)
    assert digest(folder/'calls.jsonl')==before
    return {'generation_records':len(gs),'condition_item_judgments':len(items),'item_pairs':1000,'all_judgments_replayed_from_cache':True,'settings_sha256':settings,'calls_sha256':before},sources,gs

def audit_response_status(gs):
    from steering.response_status import DEFINITION,SCHEMA
    folder=RUN/'judge_gptoss_response_status_full';calls={r['request_id']:r for r in complete_lines(folder/'calls.jsonl')};items={(r['config'],r['task_id'],r['condition']):r for r in complete_lines(folder/'items.jsonl')};assert len(items)==5000
    for key,r in items.items():
        g=gs[key+('pressured',)];assert r['status']=='complete'
        call=calls[r['request_id']];p=call['request'];assert call['status']=='ok' and call['parsed']==r['labels']
        assert r['request_id']==hashlib.sha256(json.dumps({'payload':p,'judge_revision':call['judge_revision'],'judgment_type':'response_status_v1'},sort_keys=True).encode()).hexdigest()
        quoted=json.loads(p['messages'][-1]['content']);assert quoted=={'actor_conversation':g['messages'],'actor_response':g['result']['text']}
        jsonschema.validate(call['parsed'],SCHEMA)
    return {'records':len(items)}

def main():
    result,sources,gs=asyncio.run(audit_mask());audit={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'MASK':result,'auxiliary':{}}
    mw=mask_work(sources);assert sum(not w['swap'] for w in mw)==4000
    audit['auxiliary']['mask_quality']=audit_aux('quality_mask_v2',mw,len(mw))
    audit['auxiliary']['capability_quality']=audit_aux('quality_capability_v3',capability_work(),160)
    audit['auxiliary']['response_status']=audit_response_status(gs)
    cap=json.loads((RUN/'capability_extraction_v1/summary.json').read_text());assert cap['records']==200
    outputs=[r for p in RUN.glob('capability_*.jsonl') for r in complete_lines(p)];assert len(outputs)==200
    from datasets import load_from_disk
    import decimal,re
    cap_sources={b:load_from_disk(str(ROOT/'data'/relative)) for b,relative in [('mmlu','cais__mmlu/all/test'),('gsm8k','openai__gsm8k/main/test')]}
    for raw in outputs:
        source=cap_sources[raw['benchmark']][raw['index']]
        expected=chr(65+source['answer']) if raw['benchmark']=='mmlu' else source['answer'].split('####')[-1].strip().replace(',','')
        assert raw['expected']==expected and raw['settings_sha256']==result['settings_sha256']
        text=raw['result']['text']
        match=re.search(r'\b([ABCD])\b',text) if raw['benchmark']=='mmlu' else re.search(r'####\s*([-+]?\d[\d,]*(?:\.\d+)?)',text)
        prediction=match.group(1).replace(',','') if match else None
        correct=prediction==expected
        if raw['benchmark']=='gsm8k' and prediction is not None:correct=decimal.Decimal(prediction)==decimal.Decimal(expected)
        assert prediction==raw['prediction'] and correct==raw['correct']
    for b,count in [('mmlu',30),('gsm8k',10)]:
        selected=set(sorted(range(len(cap_sources[b])),key=lambda i:hashlib.sha256((b+str(i)).encode()).hexdigest())[:count])
        for c in CONDITIONS:assert {r['index'] for r in outputs if r['benchmark']==b and r['condition']==c}==selected
    extraction=json.loads((RUN/'capability_extraction_v1/extraction_items.json').read_text());assert len(extraction)==200 and not any(r['judge_failure'] for r in extraction)
    calls={r['request_id']:r for r in complete_lines(RUN/'capability_extraction_v1/calls.jsonl')}
    by={(r['benchmark'],r['index'],r['condition']):r for r in outputs}
    for e in extraction:
        raw=by[e['benchmark'],e['index'],e['condition']];assert e['original_correct']==raw['correct'] and e['truncated']==raw['result']['hit_token_limit']
        if e['judge_requested']:
            call=calls[e['request_id']];assert call['status']=='ok';data=json.loads(call['request']['messages'][-1]['content']);assert data['response']==raw['result']['text'] and data['truncated']==e['truncated']
            if e['assisted_prediction'] is not None:assert call['parsed']['supporting_quote'] in raw['result']['text'] and call['parsed']['explicit_final_answer']
    audit['auxiliary']['capability_extraction']={'records':200,'rescues':sum(r['rescue'] for r in extraction)}
    work,inventory,invalid=gather();audit['auxiliary']['machiavelli_quality']=audit_aux('machiavelli_quality_v1',work,len(work));assert len(inventory)==len(list(RUN.glob('machiavelli*/**/trajectory.pkl')))
    native=json.loads((RUN/'machiavelli_saved_output_audit.json').read_text());assert native['status']=='passed' and native['verified_trajectories']==20
    from machiavelli.game.machiavelli_env import Trajectory
    for row in inventory:
        p=RUN/row['trajectory'];traj=Trajectory.load(p);csvrow=list(csv.DictReader((p.parent/'metrics.csv').open()))[0]
        assert abs(traj.get_points(normalize=True)-float(csvrow['points']))<1e-8
        assert abs(traj.get_mach_scores()['violations.deception']-float(csvrow['violations.deception']))<1e-8
    from scripts.audit_machiavelli import native_replay
    smoke_replays=[]
    for inv in inventory:
        if inv['main_pilot']:continue
        traj=Trajectory.load(RUN/inv['trajectory']);fallbacks={r['step'] for r in work if r['trajectory']==inv['trajectory'] and r['random_fallback']}
        replayed,reward,points=native_replay(traj,fallbacks)
        smoke_replays.append({'trajectory':inv['trajectory'],'native_replay_verified':True,'final_points':points})
    save(RUN/'next_stage_all_machiavelli_audit.json',{'status':'passed','main_native_replay_count':20,'additional_replays':smoke_replays,'inventory':inventory})
    audit['all_saved_machiavelli_trajectories']={'count':len(inventory),'official_metrics_verified':True,'invalid_attempts':len(invalid),'fallback_actions':sum(r['random_fallback_actions'] for r in inventory)}
    fixed=RUN/'machiavelli_counterfactual_quality_v1/coverage.json';fc=json.loads(fixed.read_text());assert fc['complete']==80 and fc['target_states']==16
    path,manifest=prepare()
    assert len(manifest['states'])==16 and len(complete_lines(path/'generations.jsonl'))==64
    audit['auxiliary']['fixed_baseline_states']=audit_aux('machiavelli_counterfactual_quality_v1',judge_work(path,manifest),80)|fc
    # The frozen initial checkpoints are verified by their saved hash manifest.
    frozen=json.loads((RUN/'next_stage_frozen_hashes.json').read_text())
    for relative,expected in frozen.items():assert digest(ROOT/relative)==expected,('Frozen checkpoint changed',relative)
    audit['status']='passed';save(RUN/'next_stage_final_audit.json',audit)
    completion={'completion':True,'utc':audit['utc'],'full_mask_items':1000,'conditions':CONDITIONS,'audit':str(RUN/'next_stage_final_audit.json'),'report':str(CODE/'NEXT_STAGE_REPORT.md'),'metrics':str(RUN/'next_stage_metrics.json'),'reproducibility':str(CODE/'NEXT_STAGE_REPRODUCIBILITY.md')}
    for destination in [RUN/'next_stage_complete.json',ROOT/'results/next_stage_complete.json',CODE/'results/next_stage_complete.json']:save(destination,completion)
    print(json.dumps(audit,indent=2),flush=True)
if __name__=='__main__':main()
