"""Regenerate audited tables using saved per-item outputs; no model or judge calls."""
import argparse,csv,hashlib,json
from pathlib import Path
C=['baseline','caa','sttp','rank2','pooled']
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
 for label,folder,manifest in [('mask_primary240','judge_gptoss_expanded','mask_expanded_subset.json'),('mask_partial1000','judge_gptoss_full','mask_full_test_manifest.json')]:
  result[label],ids=audit(run/folder/'items.jsonl',run/manifest,C);manifests[label]=sorted(ids)
 assert len(manifests['mask_primary240'])==240
 result['capabilities']=[]
 for benchmark,expected in [('mmlu',30),('gsm8k',10)]:
  by={c:{r['index']:r for r in lines(run/f'capability_{c}.jsonl') if r['benchmark']==benchmark} for c in C}
  assert all(set(by[c])==set(by[C[0]]) and len(by[c])==expected for c in C)
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
 assert hashlib.sha256((root/'model/fit.pt').read_bytes()).hexdigest()==read(root/'model/locked_settings.json')['fit_sha256']
 for name,rows in result.items():
  with (out/(name+'.csv')).open('w') as f:
   writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
 (out/'verified_tables.json').write_text(json.dumps(result,indent=2)+'\n')
 (root/'data/verified_item_ids.json').write_text(json.dumps(manifests,indent=2)+'\n')
 print(json.dumps({'mask_full_paired':len(manifests['mask_partial1000']),'primary_paired':240,'cp_paired':24,'locked_settings_sha256':lock,'status':'PROVISIONAL snapshot; not frozen'},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);main(p.parse_args().package.resolve())
