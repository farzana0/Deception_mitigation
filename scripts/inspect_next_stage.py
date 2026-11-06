"""One-shot read-only progress/health snapshot; no launch/restart/timer behavior."""
import collections,datetime,json,subprocess,urllib.request
from pathlib import Path
ROOT=Path('/lambda/nfs/fs-cand-nov05');RUN=ROOT/'results/steering_run'
def read(path,default):
    try:return json.loads(path.read_text())
    except (FileNotFoundError,json.JSONDecodeError):return default

def lines(path):
    if not path.exists():return []
    return [json.loads(l) for l in path.read_text().splitlines(keepends=True) if l.endswith('\n')]

def main():
    p=read(RUN/'judge_gptoss_full/paired_summary.json',{});out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'MASK_paired':p.get('paired_complete_items',0),'MASK_judge_call_statuses':p.get('judge_call_statuses',{}),'auxiliary':{},'attention':[]}
    for name,target in [('quality_mask_v2',4000),('quality_capability_v3',160),('machiavelli_quality_v1',2171),('machiavelli_counterfactual_quality_v1',80)]:
        items={r['key']:r for r in lines(RUN/name/'items.jsonl')};valid=[r for r in items.values() if r['status']=='complete'];n=sum(not r.get('swap',False) for r in valid);bad=[r['key'] for r in items.values() if r['status']!='complete']
        out['auxiliary'][name]={'complete':n,'target':target,'swaps':sum(r.get('swap',False) for r in valid),'technical_failures':len(bad)}
        validation=read(RUN/name/'validation.json',{})
        if validation.get('status')=='failed':out['attention'].append(name+': validation failed')
        if bad:out['attention'].append(name+': technical failures '+str(bad[:3]))
    out['response_status_paired']=read(RUN/'judge_gptoss_response_status_full/paired_summary.json',{}).get('paired_complete_items',0)
    out['fixed_state_generations']=len(lines(RUN/'machiavelli_counterfactual/generations.jsonl'))
    out['capability_extraction_complete']=(RUN/'capability_extraction_v1/summary.json').exists()
    out['sessions']=subprocess.run(['tmux','list-sessions','-F','#S'],capture_output=True,text=True).stdout.splitlines()
    try:
        with urllib.request.urlopen('http://127.0.0.1:8001/health',timeout=5) as f:out['judge_http']=f.status
    except Exception as e:out['judge_http']=str(e);out['attention'].append('Judge health failed')
    print(json.dumps(out),flush=True)
if __name__=='__main__':main()
