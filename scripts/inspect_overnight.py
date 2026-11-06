"""Compact read-only progress/GPU inspection for the overnight coordinator."""
import datetime,json,re,subprocess
from pathlib import Path
root=Path('/lambda/nfs/fs-cand-nov05');run=root/'results/steering_run'
print(datetime.datetime.now(datetime.timezone.utc).isoformat())
p=run/'judge_gptoss_expanded/paired_summary.json'
if p.exists():
 s=json.loads(p.read_text());print('MASK paired',s['paired_complete_items'],'/',s['target_items'],'judge',s['judge_call_statuses'])
for c in ['baseline','caa','sttp','rank2','pooled']:
 p=run/f'mask_generations_{c}.jsonl';print('MASK prompts',c,len(p.read_text().splitlines()) if p.exists() else 0)
 p=root/f'logs/machiavelli_{c}.log'
 if p.exists():
  text=p.read_text();steps=re.findall(r'([^\r\n]+):\s+\d+%[^\r\n]*?(\d+)/150',text)
  print('MACHIAVELLI',c,'saved',len(list((run/'machiavelli_main'/c).glob('seed_*/*/metrics.csv'))),'last_step',steps[-1] if steps else None,'oom',text.count('CUDA out of memory'),'tracebacks',text.count('Traceback (most recent call last)'))
print(subprocess.run(['nvidia-smi','--query-gpu=index,memory.used,utilization.gpu','--format=csv,noheader'],capture_output=True,text=True).stdout.strip())
