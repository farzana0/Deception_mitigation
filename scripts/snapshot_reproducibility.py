"""Save small method metadata in Git and full hashes beside cluster artifacts."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path('/lambda/nfs/fs-cand-nov05');RUN=ROOT/'results/steering_run';REPO=ROOT/'Deception_mitigation'
def main():
    dest=REPO/'configs/overnight';dest.mkdir(parents=True,exist_ok=True)
    names=['locked_settings.json','judge_environment.json','judge_launch.json','judge_model.json','mask_subset.json','mask_expanded_subset.json','verification.json','source_manifest.json','hf_resolved_environment.json','machiavelli_replay_validation.json']
    for name in names:
        p=RUN/name
        if p.exists():(dest/name).write_bytes(p.read_bytes())
    lock=RUN/'judge_requirements.lock'
    if lock.exists():(dest/lock.name).write_bytes(lock.read_bytes())
    paths=[p for sub in ['steering','scripts','configs/overnight','tests'] for p in (REPO/sub).rglob('*') if p.is_file() and '__pycache__' not in str(p)]
    hashes={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    artifact_names=['fit.pt','extraction.pt','locked_settings.json','mask_subset.json','mask_expanded_subset.json','locked_experiment.py']
    hashes.update({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for name in artifact_names for p in [RUN/name] if p.exists()})
    (RUN/'overnight_source_hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
if __name__=='__main__':main()
