"""One-time import of saved evidence from the verified frozen submission into this repository layout.

Every source file is checked against the frozen package SHA256SUMS. Large JSONL files are stored
gzip-compressed (mtime=0, so output is deterministic); evidence/MANIFEST.json records the original
package path, repository path and the SHA256 of the *uncompressed* bytes, which `task=rebuild`
re-verifies before using anything.

Usage: python tools/import_frozen_evidence.py --package /path/to/frozen/submission
"""
import argparse, gzip, hashlib, json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SR = 'experiments/results/steering_run'
CONDITIONS = ['baseline', 'caa', 'sttp', 'rank2', 'pooled']
GENERATION_JOURNALS = ['mask_generations.jsonl'] + [f'mask_generations_{c}.jsonl' for c in CONDITIONS + ['gpu7_helper']]

# package-relative path -> repository path ('.gz' suffix means stored compressed)
MAPPING = {
    f'{SR}/judge_gptoss_full/items.jsonl': 'evidence/mask/judge_full1000/items.jsonl.gz',
    f'{SR}/judge_gptoss_full/calls.jsonl': 'evidence/mask/judge_full1000/calls.jsonl.gz',
    f'{SR}/judge_gptoss_expanded/items.jsonl': 'evidence/mask/judge_original240/items.jsonl.gz',
    f'{SR}/judge_gptoss_expanded/calls.jsonl': 'evidence/mask/judge_original240/calls.jsonl.gz',
    **{f'{SR}/{name}': f'evidence/mask/generations/{name}.gz' for name in GENERATION_JOURNALS},
    **{f'{SR}/capability_{c}.jsonl': f'evidence/capability/capability_{c}.jsonl' for c in CONDITIONS},
    f'{SR}/machiavelli_saved_output_audit.json': 'evidence/machiavelli/machiavelli_saved_output_audit.json',
    f'{SR}/calibration.jsonl': 'evidence/calibration/calibration.jsonl',
    f'{SR}/locked_experiment.py': 'models/locked/locked_experiment.py',
    f'{SR}/mask_full_test_manifest.json': 'data/manifests/mask_full1000.json',
    f'{SR}/mask_expanded_subset.json': 'data/manifests/mask_original240.json',
    f'{SR}/mask_subset.json': 'data/manifests/mask_pilot12.json',
    'experiments/results/cp_exploratory/pilot_judgments.jsonl': 'evidence/cp/pilot_judgments.jsonl',
    'experiments/results/cp_exploratory/pilot_manifest.json': 'data/manifests/cp_pilot24.json',
    'experiments/cohort_selection.json': 'reproduction/provenance/cohort_selection.json',
    'experiments/mask_evidence_verification.json': 'reproduction/provenance/mask_evidence_verification.json',
    'experiments/provenance.json': 'reproduction/provenance/provenance.json',
    'experiments/snapshot_provenance.json': 'reproduction/provenance/snapshot_provenance.json',
    'model/source_manifest.json': 'reproduction/provenance/source_manifest.json',
    'model/fit.pt': 'models/steering_fits/fit.pt',
    'model/cp_fit.pt': 'models/steering_fits/cp_fit.pt',
    'model/locked_settings.json': 'models/locked/locked_settings.json',
    'model/locked_cp_settings.json': 'models/locked/locked_cp_settings.json',
    'model/predeclared_protocol.json': 'models/locked/cp_predeclared_protocol.json',
    'model/judge_model.json': 'models/judge/judge_model.json',
    'model/judge_requirements.lock': 'models/judge/judge_requirements.lock',
    'model/base_weight_verification.json': 'models/base/base_weight_verification.json',
    'model/hf_resolved_environment.json': 'models/base/hf_resolved_environment.json',
    'model/hf_system_requirements.lock': 'models/base/hf_system_requirements.lock',
    'data/qwen_contrast_pairs.jsonl': 'data/contrast_pairs/qwen_contrast_pairs.jsonl',
    'data/steering_splits.json': 'data/manifests/steering_splits.json',
    'data/input_manifest.json': 'data/manifests/input_manifest.json',
    'data/input_setup.json': 'data/manifests/input_setup.json',
    'data/cais__mmlu/all/test/dataset_info.json': 'data/dataset_info/cais__mmlu_all_test.json',
    'data/openai__gsm8k/main/test/dataset_info.json': 'data/dataset_info/openai__gsm8k_main_test.json',
    # Frozen outputs used as the comparison target for the offline rebuild.
    'data/verified_item_ids.json': 'results/frozen/verified_item_ids.json',
    'report/report.md': 'results/frozen/report.md',
    'report/report.pdf': 'results/frozen/report.pdf',
    **{f'report/tables/{n}': f'results/frozen/tables/{n}' for n in ['capabilities.csv', 'cp_exploratory.csv', 'machiavelli.csv', 'mask_diagnostics.csv', 'mask_full1000.csv', 'mask_original240.csv', 'paired_diagnostics.json', 'verified_tables.json']},
    **{f'report/figures/{n}': f'results/frozen/figures/{n}' for n in ['mask_main.png', 'mask240.png'] + [f'page_{i:02d}.png' for i in range(1, 11)]},
}

def main(package):
    sums = dict(reversed(line.split('  ', 1)) for line in (package / 'SHA256SUMS').read_text().splitlines())
    records = []
    for source, target in MAPPING.items():
        data = (package / source).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        assert sums[source] == digest, f'{source} does not match frozen SHA256SUMS'
        out = REPO / target
        out.parent.mkdir(parents=True, exist_ok=True)
        if target.endswith('.gz'):
            with open(out, 'wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', compresslevel=9, mtime=0, filename='') as f:
                f.write(data)
        else:
            out.write_bytes(data)
        records.append({'package_path': source, 'repo_path': target, 'sha256': digest, 'bytes': len(data)})
    manifest = {'source': 'Verified frozen CAIS submission (sealed archive sha256 102bcb12a695be6cca65015cad8b2366d777d0825bf72f633e666e0bf91ef454)',
                'sha256_of': 'uncompressed original bytes, identical to the frozen package SHA256SUMS', 'files': records}
    (REPO / 'evidence/MANIFEST.json').write_text(json.dumps(manifest, indent=1) + '\n')
    print(len(records), 'files imported and verified')

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--package', type=Path, required=True)
    main(p.parse_args().package.resolve())
