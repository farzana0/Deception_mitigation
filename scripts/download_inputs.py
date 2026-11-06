import json, subprocess, time, traceback, hashlib
from pathlib import Path
from huggingface_hub import HfApi, hf_hub_download
from datasets import load_dataset
r=Path('/lambda/nfs/fs-cand-nov05')
manifest=r/'results/input_manifest.json'
state=json.loads(manifest.read_text()) if manifest.exists() else {}
def save(): manifest.write_text(json.dumps(state,indent=2)+'\n')
errors=[]
repos={'activation-steering-4-honesty':'https://github.com/Tara-Research/activation-steering-4-honesty','mask':'https://github.com/centerforaisafety/mask','simple-evals':'https://github.com/centerforaisafety/simple-evals'}
for name,url in repos.items():
 try:
  dest=r/'repos'/name
  if not dest.exists(): subprocess.run(['git','clone',url,str(dest)],check=True)
  pinned=state.get(name,{}).get('revision')
  if pinned: subprocess.run(['git','checkout','--detach',pinned],cwd=dest,check=True)
  sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=dest,text=True).strip()
  state[name]={'url':url,'revision':sha,'path':str(dest)};save()
  print('READY repo',name,sha,flush=True)
 except Exception as e: errors.append(str(e));traceback.print_exc()
api=HfApi()
for repo, configs in [('cais/MASK',['continuations','disinformation','doubling_down_known_facts','known_facts','provided_facts','statistics']),('cais/mmlu',['all']),('openai/gsm8k',['main'])]:
 try:
  sha=state.get(repo,{}).get('revision') or api.dataset_info(repo).sha
  state.setdefault(repo,{'revision':sha,'splits':{}});save()
  for config in configs:
   dest=r/'data'/repo.replace('/','__')/config/'test'
   if dest.exists(): print('EXISTS',dest,flush=True);continue
   print('DOWNLOADING',repo,config,'test',sha,flush=True)
   ds=load_dataset(repo,config,split='test',revision=sha)
   ds.save_to_disk(str(dest))
   state[repo]['splits'][config]={'split':'test','rows':len(ds),'path':str(dest),'columns':ds.column_names};save()
   print('READY',repo,config,len(ds),flush=True)
 except Exception as e: errors.append(str(e));traceback.print_exc()
try:
 repo='justinphan3110/machiavelli'
 sha=state.get(repo,{}).get('revision') or api.dataset_info(repo).sha
 state[repo]={'revision':sha};save()
 print('DOWNLOADING game_data.zip',sha,flush=True)
 p=hf_hub_download(repo,'game_data.zip',repo_type='dataset',revision=sha,local_dir=r/'data/machiavelli')
 import zipfile
 with zipfile.ZipFile(p) as z:
  root=(r/'data/machiavelli/extracted').resolve()
  for member in z.infolist():
   if not (root/member.filename).resolve().is_relative_to(root): raise ValueError('Unsafe archive path')
  z.extractall(root)
 state[repo].update(path=p,extracted=str(root));save()
 print('READY machiavelli',flush=True)
except Exception as e: errors.append(str(e));traceback.print_exc()
state['errors']=errors;save()
print('FINISHED',json.dumps(errors),flush=True)
raise SystemExit(bool(errors))
