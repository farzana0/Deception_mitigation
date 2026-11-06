"""Hydra configs compose for every option group and agree with the locked artifacts (no GPU, no torch)."""
import json, unittest
from pathlib import Path

from hydra import compose, initialize_config_dir

from cais.workspace import REPO, check_locked, jsonl, repo_path, sha256
import cais.cli  # registers the repo_root resolver

GROUPS = {g: sorted(p.stem for p in (REPO / 'conf' / g).glob('*.yaml'))
          for g in ['task', 'model', 'intervention', 'dataset', 'judge_model', 'judge_rubric']}


def compose_with(**overrides):
    with initialize_config_dir(config_dir=str(REPO / 'conf'), version_base='1.3'):
        return compose('config', overrides=[f'{k}={v}' for k, v in overrides.items()])


class ConfigTest(unittest.TestCase):
    def test_every_group_option_composes(self):
        for group, options in GROUPS.items():
            for option in options:
                cfg = compose_with(**{group: option}, **({'task.package': '/x'} if option == 'audit' else {}))
                self.assertTrue(cfg.paths.run)

    def test_interventions_match_locked_settings(self):
        for option in GROUPS['intervention']:
            check_locked(compose_with(intervention=option))

    def test_dataset_manifests_exist_with_expected_sizes(self):
        for option in GROUPS['dataset']:
            cfg = compose_with(dataset=option)
            if cfg.dataset.kind == 'mask':
                items = json.loads(repo_path(cfg.dataset.manifest).read_text())['items']
                self.assertEqual(len(items), cfg.dataset.n_items)
                self.assertEqual(len({(i['config'], i['task_id']) for i in items}), cfg.dataset.n_items)

    def test_evidence_manifest_hashes(self):
        manifest = json.loads((REPO / 'evidence/MANIFEST.json').read_text())
        for record in manifest['files']:
            path = REPO / record['repo_path']
            if not path.name.endswith('.gz'):
                self.assertEqual(sha256(path), record['sha256'], record['repo_path'])

    def test_quick_subset_is_first_item_per_config_of_pilot12(self):
        pilot = json.loads((REPO / 'data/manifests/mask_pilot12.json').read_text())['items']
        quick = json.loads((REPO / 'data/manifests/mask_quick6.json').read_text())['items']
        first = {}
        for item in pilot:
            first.setdefault(item['config'], item)
        self.assertEqual(quick, list(first.values()))


if __name__ == '__main__':
    unittest.main()
