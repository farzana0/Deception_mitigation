"""Compact read-only progress/GPU inspection for the overnight coordinator."""
import datetime,json,re,subprocess
from pathlib import Path
root=Path('/lambda/nfs/fs-cand-nov05');run=root/'results/steering_run'
print(datetime.datetime.now(datetime.timezone.utc).isoformat())
p=run/'judge_gptoss_expanded/paired_summary.json'
if p.exists():
 s=json.loads(p.read_text());print('MASK paired',s['paired_complete_items'],'/',s['target_items'],'judge',s['judge_call_statuses'])
aux=run/'judge_gptoss_response_status/paired_summary.json'
if aux.exists():
 a=json.loads(aux.read_text());print('AUX response status',sum(v['complete_items'] for v in a['conditions'].values()),'/1200 records; paired',a['paired_complete_items'],'/240',a['judge_call_statuses'])
prompt_keys=set()
for journal in run.glob('mask_generations*.jsonl'):
 for line in journal.read_text().splitlines(keepends=True):
  if not line.endswith('\n'):continue
  record=json.loads(line);prompt_keys.add(tuple(record[k] for k in ['config','task_id','condition','prompt_type']))
for c in ['baseline','caa','sttp','rank2','pooled']:
 print('MASK prompts',c,sum(k[2]==c for k in prompt_keys))
 p=root/f'logs/machiavelli_{c}.log'
 if p.exists():
  text=p.read_text();steps=re.findall(r'([^\r\n]+):\s+\d+%[^\r\n]*?(\d+)/150',text)
  print('MACHIAVELLI',c,'saved',len(list((run/'machiavelli_main'/c).glob('seed_*/*/metrics.csv'))),'last_step',steps[-1] if steps else None,'oom',text.count('CUDA out of memory'),'tracebacks',text.count('Traceback (most recent call last)'))
print(subprocess.run(['nvidia-smi','--query-gpu=index,memory.used,utilization.gpu','--format=csv,noheader'],capture_output=True,text=True).stdout.strip())

# Preserve actual process-to-GPU assignments without recording other environment values.
apps=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader,nounits'],capture_output=True,text=True).stdout
snapshot={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'processes':[]}
for line in apps.splitlines():
    fields=[v.strip() for v in line.split(',')]
    if len(fields)!=3:continue
    pid,uuid,memory=fields
    try:
        proc=Path('/proc')/pid
        command=proc.joinpath('cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace').strip()
        cuda=next((v.split(b'=',1)[1].decode(errors='replace') for v in proc.joinpath('environ').read_bytes().split(b'\0') if v.startswith(b'CUDA_VISIBLE_DEVICES=')),None)
    except (OSError,ProcessLookupError):continue
    snapshot['processes'].append({'pid':int(pid),'gpu_uuid':uuid,'memory_mib':memory,'command':command,'CUDA_VISIBLE_DEVICES':cuda})
with (run/'gpu_process_snapshots.jsonl').open('a') as f:f.write(json.dumps(snapshot)+'\n')
