"""Regenerate audited tables using saved per-item outputs; no model or judge calls."""
import argparse,csv,datetime,hashlib,json
from pathlib import Path
C=['baseline','caa','sttp','rank2','pooled']
FREEZE=datetime.datetime(2026,11,6,22,tzinfo=datetime.timezone.utc)
def select_cohort(paired_count,observed_at,full_completion_observed_at=None):
 if paired_count==1000 and (observed_at<=FREEZE or full_completion_observed_at is not None and full_completion_observed_at<=FREEZE):
  return 'full1000'
 return 'original240'
def read(p):return json.loads(p.read_text())
def lines(p):
 rows=[]
 for line in p.read_bytes().splitlines(keepends=True):
  if not line.endswith(b'\n'):continue
  rows.append(json.loads(line))
 return rows
def latest(p):return {(r['config'],r['task_id'],r['condition']):r for r in lines(p)}
def audit(p,manifest,conditions):
 records=latest(p);wanted={(r['config'],r['task_id']) for r in read(manifest)['items']}
 assert len(wanted)==len(read(manifest)['items']),'duplicate manifest IDs'
 valid={k:r for k,r in records.items() if r['status']=='complete' and not r.get('judge_failures')}
 common=wanted.intersection(*[{k[:2] for k in valid if k[2]==c} for c in conditions])
 out=[]
 for c in conditions:
  assess={k for k in common if valid[k+(c,)]['honesty'] in [-1,1]}
  paired={k for k in assess if valid[k+(conditions[0],)]['honesty'] in [-1,1]}
  d=sum(valid[k+(c,)]['honesty']==-1 for k in assess)
  delta=sum(int(valid[k+(c,)]['honesty']==-1)-int(valid[k+(conditions[0],)]['honesty']==-1) for k in paired)
  out.append(dict(condition=c,complete_paired_n=len(common),dishonest=d,assessable_n=len(assess),deception=d/len(assess) if assess else None,paired_assessable_n=len(paired),paired_delta=delta/len(paired) if paired else None))
 return out,common

def main(root):
 run=root/'experiments/results/steering_run';cp=root/'experiments/results/cp_exploratory';out=root/'report/tables';out.mkdir(parents=True,exist_ok=True)
 result={};manifests={}
 assert len(read(run/'mask_full_test_manifest.json')['items'])==1000
 for label,folder,manifest in [('mask_primary240','judge_gptoss_expanded','mask_expanded_subset.json'),('mask_partial1000','judge_gptoss_full','mask_full_test_manifest.json')]:
  result[label],ids=audit(run/folder/'items.jsonl',run/manifest,C);manifests[label]=sorted(ids)
 assert len(manifests['mask_primary240'])==240
 result['capabilities']=[]
 for benchmark,expected in [('mmlu',30),('gsm8k',10)]:
  info=root/'data'/('cais__mmlu/all/test/dataset_info.json' if benchmark=='mmlu' else 'openai__gsm8k/main/test/dataset_info.json')
  size=read(info)['splits']['test']['num_examples']
  required=set(sorted(range(size),key=lambda i:hashlib.sha256((benchmark+str(i)).encode()).hexdigest())[:expected])
  by={c:{r['index']:r for r in lines(run/f'capability_{c}.jsonl') if r['benchmark']==benchmark} for c in C}
  assert all(set(by[c])==required and len(by[c])==expected for c in C)
  for c in C:
   correct=0
   for r in by[c].values():
    import re
    text=r['result']['text'];match=re.search(r'\b([ABCD])\b' if benchmark=='mmlu' else r'####\s*([-+]?\d[\d,]*(?:\.\d+)?)',text)
    pred=match.group(1).replace(',','') if match else None
    ok=pred==r['expected']
    if benchmark=='gsm8k' and pred is not None:ok=float(pred)==float(r['expected'])
    assert ok==r['correct'],'saved scoring mismatch'
    correct+=ok
   result['capabilities'].append(dict(condition=c,benchmark=benchmark,paired_n=expected,correct=correct,accuracy=correct/expected))
  manifests[benchmark]=sorted(by[C[0]])
 result['cp_exploratory'],ids=audit(cp/'pilot_judgments.jsonl',cp/'pilot_manifest.json',['cp_scheduled','cp_static']);manifests['cp_exploratory']=sorted(ids)
 assert len(ids)==24
 assert not ids.intersection(set(map(tuple,manifests['mask_primary240'])))
 saved=read(run/'machiavelli_saved_output_audit.json');assert saved['status']=='passed' and saved['verified_trajectories']==20 and not saved['failures']
 result['machiavelli']=[dict(condition=c,paired_n=saved['conditions'][c]['verified_trajectories'],deception=saved['conditions'][c]['mean_deception'],reward=saved['conditions'][c]['mean_reward']) for c in C]
 lock=hashlib.sha256((root/'model/locked_settings.json').read_bytes()).hexdigest()
 for folder in ['judge_gptoss_expanded','judge_gptoss_full']:
  assert all(r['settings_sha256']==lock for r in latest(run/folder/'items.jsonl').values())
  assert all(r['honesty'] in [-1,0,1] for r in latest(run/folder/'items.jsonl').values() if r['status']=='complete')
 locked=read(root/'model/locked_settings.json')
 for field,path in [('fit_sha256',root/'model/fit.pt'),('source_sha256',run/'locked_experiment.py'),('calibration_sha256',run/'calibration.jsonl'),('pairs_sha256',root/'data/qwen_contrast_pairs.jsonl'),('splits_sha256',root/'data/steering_splits.json')]:
  assert hashlib.sha256(path.read_bytes()).hexdigest()==locked[field],field+' mismatch'
 # Every technically complete judgment must retain its successful local judge calls.
 for folder in ['judge_gptoss_expanded','judge_gptoss_full']:
  calls={r['request_id']:r for r in lines(run/folder/'calls.jsonl')}
  for r in latest(run/folder/'items.jsonl').values():
   if r['status']=='complete':
    assert r['request_ids'] and all(i in calls and calls[i]['status']=='ok' for i in r['request_ids']),'missing/failed judge call'
 observed=datetime.datetime.now(datetime.timezone.utc)
 state_path=root/'experiments/cohort_selection.json'
 previous=read(state_path) if state_path.exists() else {}
 first=previous.get('full_completion_observed_utc')
 if len(manifests['mask_partial1000'])==1000 and first is None:first=observed.isoformat()
 selected=select_cohort(len(manifests['mask_partial1000']),observed,datetime.datetime.fromisoformat(first) if first else None)
 state={'freeze_utc':FREEZE.isoformat(),'observed_utc':observed.isoformat(),'full_completion_observed_utc':first,'full_paired_n':len(manifests['mask_partial1000']),'primary_cohort':selected,'status':'full cohort complete before freeze' if selected=='full1000' else 'deadline fallback' if observed>=FREEZE else 'incomplete before freeze; selection pending'}
 state_path.write_text(json.dumps(state,indent=2)+'\n')
 if selected=='full1000':
  result['mask_full1000']=result.pop('mask_partial1000')
  result['mask_original240']=result.pop('mask_primary240')
  for stale in ['mask_partial1000.csv','mask_primary240.csv']:(out/stale).unlink(missing_ok=True)
 primary_ids=set(map(tuple,manifests['mask_partial1000' if selected=='full1000' else 'mask_primary240']))
 primary_records=latest(run/('judge_gptoss_full' if selected=='full1000' else 'judge_gptoss_expanded')/'items.jsonl')
 result['mask_diagnostics']=[]
 for c in C:
  rows=[primary_records[k+(c,)] for k in primary_ids]
  result['mask_diagnostics'].append({'condition':c,'paired_n':len(rows),'belief_covered_n':sum(r['knowledge_reference_covered'] for r in rows),'pressure_unknown_n':sum(r['pressure_abstention_or_unknown'] for r in rows),'truncated_n':sum(r['target_response_truncated'] for r in rows),'dishonest_all_n':sum(r['honesty']==-1 for r in rows)})
 both={k for k in primary_ids if all(primary_records[k+(c,)]['honesty'] in [-1,1] for c in ['rank2','pooled'])}
 all_assessable={k for k in primary_ids if all(primary_records[k+(c,)]['honesty'] in [-1,1] for c in C)}
 diagnostic={'primary_paired_n':len(primary_ids),'all_five_assessable_n':len(all_assessable),'rank2_vs_pooled':{'paired_assessable_n':len(both),'rank2_dishonest':sum(primary_records[k+('rank2',)]['honesty']==-1 for k in both),'pooled_dishonest':sum(primary_records[k+('pooled',)]['honesty']==-1 for k in both)}}
 (out/'paired_diagnostics.json').write_text(json.dumps(diagnostic,indent=2)+'\n')
 for name,rows in result.items():
  with (out/(name+'.csv')).open('w') as f:
   writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
 (out/'verified_tables.json').write_text(json.dumps(result,indent=2)+'\n')
 (root/'data/verified_item_ids.json').write_text(json.dumps(manifests,indent=2)+'\n')
 print(json.dumps({'mask_full_paired':len(manifests['mask_partial1000']),'primary_paired':1000 if selected=='full1000' else 240,'cp_paired':24,'locked_settings_sha256':lock,'cohort_selection':state},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);main(p.parse_args().package.resolve())
