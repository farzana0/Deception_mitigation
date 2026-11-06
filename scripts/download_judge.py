import json
from pathlib import Path
from huggingface_hub import HfApi,snapshot_download
r=Path('/lambda/nfs/fs-cand-nov05')
file=r/'results/steering_run/judge_model.json'
revision=json.loads(file.read_text())['revision'] if file.exists() else HfApi().model_info('openai/gpt-oss-20b').sha
record={'model':'openai/gpt-oss-20b','revision':revision,'local_path':str(r/'models/gpt-oss-20b')}
file.write_text(json.dumps(record,indent=2)+'\n');print(record,flush=True)
snapshot_download('openai/gpt-oss-20b',revision=revision,local_dir=r/'models/gpt-oss-20b',max_workers=8,ignore_patterns=['original/*','*.pt'])
(r/'results/steering_run/judge_download.complete').write_text(revision+'\n')
print('JUDGE DOWNLOAD COMPLETE',flush=True)
