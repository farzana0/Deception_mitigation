import json,time
from pathlib import Path
r=Path('/lambda/nfs/fs-cand-nov05')
while not (r/'results/download_inputs.exitcode').exists():
 p=r/'data/machiavelli/game_data.zip'
 count=sum(1 for _ in (r/'data/machiavelli/extracted').rglob('*')) if (r/'data/machiavelli/extracted').exists() else 0
 print('DOWNLOAD PROGRESS', 'game_zip_bytes',p.stat().st_size if p.exists() else 0,'extracted_entries',count,flush=True)
 time.sleep(20)
status=int((r/'results/download_inputs.exitcode').read_text())
if status: raise RuntimeError('Input downloads failed; see logs/download_inputs.log')
m=json.loads((r/'results/input_manifest.json').read_text())
root=Path(m['justinphan3110/machiavelli']['extracted'])
data=root/'game_data'
assert data.is_dir(), list(root.iterdir())
link=r/'repos/simple-evals/machiavelli_eval/game_data'
if not link.exists(): link.symlink_to(data,target_is_directory=True)
assert (link/'scenarios').is_dir()
print('READY: pinned Machiavelli game data linked to official runner',link,flush=True)
(r/'results/input_setup.json').write_text(json.dumps({'status':'passed','game_data':str(link),'dataset_manifest':str(r/'results/input_manifest.json')},indent=2)+'\n')
