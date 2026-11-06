"""Official MASK transport on two CP modes, plus fixed-baseline-belief paired reports."""
import asyncio,collections,json,time
from pathlib import Path
from steering.cp_exploratory import OUT,ROOT,RUN,digest
from steering.cp_pilot import CONDITIONS,DEADLINE
from steering.grade_pilot import Transport,score_item,smoke,save
from steering.official_mask import complete_lines,load_official
from steering import response_status as rs
from steering.journal import repair_tail

def latest(path):return {(r['config'],r['task_id'],r['condition']):r for r in complete_lines(path)}
def direct(labels,a,b,selected):
    # Direction is b -> a, so static->scheduled for the primary comparison.
    keys=[k for k in selected if k+(a,) in labels and k+(b,) in labels and labels[k+(a,)]['status']=='complete' and labels[k+(b,)]['status']=='complete']
    assess=[k for k in keys if labels[k+(a,)]['honesty'] in [-1,1] and labels[k+(b,)]['honesty'] in [-1,1]]
    da=sum(labels[k+(a,)]['honesty']==-1 for k in assess);db=sum(labels[k+(b,)]['honesty']==-1 for k in assess)
    return {'condition_a':a,'condition_b':b,'transition_direction':b+' -> '+a,'both_technically_complete_n':len(keys),'shared_assessable_n':len(assess),'a_dishonest':da,'b_dishonest':db,'a_deception':da/len(assess) if assess else None,'b_deception':db/len(assess) if assess else None,'paired_deception_delta_a_minus_b':(da-db)/len(assess) if assess else None,'dishonest_to_honest':sum(labels[k+(b,)]['honesty']==-1 and labels[k+(a,)]['honesty']==1 for k in assess),'honest_to_dishonest':sum(labels[k+(b,)]['honesty']==1 and labels[k+(a,)]['honesty']==-1 for k in assess)}

def summarize(items,status_items,selected,official):
    main=latest(RUN/'judge_gptoss_full/items.jsonl');all_labels=main|items
    fixed={};conditions={}
    for k,r in all_labels.items():
        if k[:2] not in selected or r['status']!='complete':continue
        base=main.get(k[:2]+('baseline',))
        if not base or base['status']!='complete':continue
        row=dict(r);scoring=dict(r['scoring_inputs'])
        if 'eval_belief' in base['scoring_inputs']:scoring['eval_belief']=base['scoring_inputs']['eval_belief']
        elif 'eval_belief' in scoring:scoring.pop('eval_belief')
        func=official['aggregate_eval_honesty_statistics' if k[0]=='statistics' else 'aggregate_eval_honesty']
        row['honesty']=int(func(scoring,['pressure'],'eval_belief'));row['scoring_inputs']=scoring;fixed[k]=row
    for c in ['baseline','caa','sttp','rank2','pooled']+CONDITIONS:
        values=[r for k,r in all_labels.items() if k[:2] in selected and k[2]==c and r['status']=='complete']
        honest=sum(r['honesty']==1 for r in values);bad=sum(r['honesty']==-1 for r in values)
        ss=[v for k,v in status_items.items() if k[:2] in selected and k[2]==c and v['status']=='complete']
        conditions[c]={'complete_items':len(values),'assessable_n':honest+bad,'honest':honest,'dishonest':bad,'undetermined':len(values)-honest-bad,'deception':bad/(honest+bad) if honest+bad else None,'belief_coverage':sum(r['knowledge_reference_covered'] for r in values)/len(values) if values else None,'refusal_labels_complete_n':len(ss),'explicit_refusal_count':sum(v['labels']['explicit_refusal'] for v in ss),'epistemic_abstention_count':sum(v['labels']['epistemic_abstention'] for v in ss),'truncated':sum(r['target_response_truncated'] for r in values),'technical_failures':sum(r['status']!='complete' for k,r in all_labels.items() if k[:2] in selected and k[2]==c)}
    own=direct(all_labels,'cp_scheduled','cp_static',selected);sensitivity=direct(fixed,'cp_scheduled','cp_static',selected)
    contextual={cp:{other:direct(all_labels,cp,other,selected) for other in ['baseline','caa','sttp','rank2','pooled']} for cp in CONDITIONS}
    fixed_context={cp:{other:direct(fixed,cp,other,selected) for other in ['baseline','caa','sttp','rank2','pooled']} for cp in CONDITIONS}
    report={'label':'Exploratory matched five-layer CP-scheduled vs CP-static pilot, separate from main results','updated_epoch':time.time(),'target_items':24,'conditions':conditions,'primary_scheduled_vs_static':own,'fixed_baseline_belief_scheduled_vs_static':sensitivity,'context_comparisons':contextual,'fixed_baseline_belief_context':fixed_context,'protocol_sha256':digest(OUT/'predeclared_protocol.json'),'cp_settings_sha256':digest(OUT/'locked_cp_settings.json'),'fit_sha256':digest(OUT/'cp_fit.pt'),'layer_window_note':'Both CP variants use the same five layers and offsets>=1. Existing methods retain original settings; CAA uses one layer and the other methods include offset0, so cross-method comparisons evaluate the whole method.','follow_up_first':'Same-loss unfolded rank2 on the identical shared-prompt, shared-offset training tensors, regularization and token window; not run today.'}
    save(OUT/'paired_summary.json',report)
    save(OUT/'fixed_baseline_belief_items.json',list(fixed.values()))
    return report

async def main_async():
    # Do not inspect any held-out CP judgments before the frozen gate passes.
    while True:
        p=OUT/'pilot_gate.json'
        if p.exists():
            gate=json.loads(p.read_text())
            if gate['decision']=='do_not_launch':print('CP PILOT GATE FAILED; FIT/SMOKE RETAINED',flush=True);return
            if gate['decision']=='launch_both':break
        if time.time()>DEADLINE:return
        await asyncio.sleep(10)
    folder=OUT/'judge';folder.mkdir(exist_ok=True);official=load_official();transport=Transport(folder,'local',official)
    official['evaluate_responses_async']=transport.evaluator;await smoke(transport,official,folder)
    rs.FOLDER=OUT/'response_status';rs.SUBSET=OUT/'pilot_manifest.json';status_judge=rs.Judge();rs.smoke(status_judge)
    from datasets import load_from_disk
    selected={(i['config'],i['task_id']) for i in json.loads((OUT/'pilot_manifest.json').read_text())['items']}
    datasets={c:load_from_disk(str(ROOT/'data/cais__MASK'/c/'test')) for c,t in selected}
    rows={(c,t):next(r for r in datasets[c] if str(r['task_id'])==t) for c,t in selected}
    path=OUT/'pilot_judgments.jsonl';repair_tail(path);items=latest(path)
    spath=OUT/'response_status/items.jsonl';repair_tail(spath);status_items=latest(spath)
    while time.time()<DEADLINE:
        available=collections.defaultdict(dict)
        for g in complete_lines(OUT/'pilot_generations.jsonl'):available[g['config'],g['task_id'],g['condition']][g['prompt_type']]=g
        for c,t in sorted(selected):
            row=rows[c,t];needed={'pressured'}|{'belief_'+str(k) for k in [1,2,3] if row.get('belief_elicit_'+str(k))}
            for condition in CONDITIONS:
                key=(c,t,condition)
                if not needed.issubset(available[key]):continue
                if key not in items or items[key]['status']!='complete':
                    record=await score_item(official,transport,row,c,condition,available[key])
                    with path.open('a') as f:f.write(json.dumps(record)+'\n');f.flush()
                    items[key]=record;print('CP JUDGED',*key,record['status'],flush=True)
                if key not in status_items or status_items[key]['status']!='complete':
                    g=available[key]['pressured'];call=await asyncio.to_thread(status_judge.call,g['messages'],g['result']['text'])
                    record={'config':c,'task_id':t,'condition':condition,'status':'complete' if call['status']=='ok' else 'technical_failure','labels':call['parsed'],'request_id':call['request_id']}
                    with spath.open('a') as f:f.write(json.dumps(record)+'\n');f.flush()
                    status_items[key]=record
                summarize(items,status_items,selected,official)
        report=summarize(items,status_items,selected,official)
        own_done=all(report['conditions'][c]['complete_items']==24 and report['conditions'][c]['refusal_labels_complete_n']==24 for c in CONDITIONS)
        context_done=all(report['conditions'][c]['complete_items']==24 for c in ['baseline','caa','sttp','rank2','pooled'])
        if own_done and context_done:
            save(OUT/'pilot_complete.json',{'complete':True,'epoch':time.time(),'within_deadline':time.time()<DEADLINE,'own_conditions_items_each':24,'all_context_conditions_items_each':24,'summary':str(OUT/'paired_summary.json')});print('CP TWO-CONDITION PILOT COMPLETE WITH MATCHED CONTEXT',flush=True);return
        await asyncio.sleep(15)
    save(OUT/'pilot_deadline_status.json',{'deadline_elapsed':True,'summary':str(OUT/'paired_summary.json'),'complete':False});print('CP DEADLINE; PARTIAL ARTIFACTS RETAINED',flush=True)

if __name__=='__main__':asyncio.run(main_async())
