"""Copy a portable saved-evidence package without logs, base weights or extraction checkpoints."""
import argparse,errno,json,shutil,subprocess,time
from pathlib import Path
EXCLUDED={'extraction.pt','matched_activations.pt','mask_prompt_leases','__pycache__','.git','game_data'}
def copy_file(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True)
 for attempt in range(8):
  try:
   data=src.read_bytes();dst.write_bytes(data);return
  except OSError as error:
   if error.errno not in {errno.ESTALE,errno.EIO,errno.EINTR,errno.EAGAIN} or attempt==7:raise
   time.sleep(.1)
def copy_tree(src,dst):
 dst.mkdir(parents=True,exist_ok=True)
 for child in src.iterdir():
  if child.name in EXCLUDED or child.suffix=='.lock' or '.interrupted-tail-' in child.name or child.is_symlink():continue
  if child.is_dir():copy_tree(child,dst/child.name)
  elif child.is_file():copy_file(child,dst/child.name)
def main(source,code,target):
 assert target!=source and not target.is_relative_to(source),'Choose a separate package directory'
 for directory in ['report/tables','report/figures','model','data','experiments']:(target/directory).mkdir(parents=True,exist_ok=True)
 copy_tree(code,target/'experiments/code');copy_tree(source/'results',target/'experiments/results')
 for name in ['cais__MASK','cais__mmlu','openai__gsm8k']:copy_tree(source/'data'/name,target/'data'/name)
 for name in ['mask','simple-evals','activation-steering-4-honesty']:copy_tree(source/'repos'/name,target/'experiments/upstream'/name)
 for name in ['fit.pt','locked_settings.json','hf_resolved_environment.json','hf_system_requirements.lock','judge_model.json','judge_requirements.lock','source_manifest.json']:copy_file(source/'results/steering_run'/name,target/'model'/name)
 for name in ['cp_fit.pt','locked_cp_settings.json','predeclared_protocol.json']:copy_file(source/'results/cp_exploratory'/name,target/'model'/name)
 for name in ['input_manifest.json','input_setup.json','steering_splits.json','qwen_contrast_pairs.jsonl']:copy_file(source/'results'/name,target/'data'/name)
 for name in ['WAKEUP_STATUS.md','RESULTS_NOW.md']:copy_file(source/name,target/'experiments'/name)
 (target/'experiments/snapshot_provenance.json').write_text(json.dumps({'source_code_commit':subprocess.check_output(['git','-C',str(source/'Deception_mitigation'),'rev-parse','HEAD'],text=True).strip(),'packaging_code_commit':subprocess.check_output(['git','-C',str(code),'rev-parse','HEAD'],text=True).strip(),'source_root':str(source),'source_worktree_status':subprocess.check_output(['git','-C',str(source/'Deception_mitigation'),'status','--short'],text=True),'packaging_worktree_status':subprocess.check_output(['git','-C',str(code),'status','--short'],text=True)},indent=2)+'\n')
 print(target)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--code-root',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args();main(a.source_root.resolve(),a.code_root.resolve(),a.destination.resolve())
