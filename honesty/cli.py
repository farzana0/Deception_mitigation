"""Honesty-steering experiments: one Hydra CLI over the existing steering/ and scripts/ code.

    python -m honesty task=rebuild                                   # offline, from saved evidence
    python -m honesty -m task=generate dataset=mask_quick6 intervention=baseline,caa,sttp,rank2,pooled
    python -m honesty task=judge dataset=mask_quick6
    python -m honesty task=report dataset=mask_quick6

See README.md for the full set of commands and conf/ for every option.
"""
import asyncio, importlib, json, os, runpy, sys
from argparse import Namespace
from pathlib import Path

import hydra
from omegaconf import OmegaConf

from honesty.workspace import REPO, CONDITIONS, bind, check_locked, materialize_package, repo_path, run_workspace

sys.path.insert(0, str(REPO))
OmegaConf.register_new_resolver('repo_root', lambda: str(REPO), replace=True)


def save_resolved(cfg):
    from hydra.core.hydra_config import HydraConfig
    out = Path(HydraConfig.get().runtime.output_dir)
    (out / 'resolved_config.yaml').write_text(OmegaConf.to_yaml(cfg, resolve=True))
    return out


def run_script(name, *args):
    """Run an existing argparse script from scripts/ in this process."""
    sys.argv = [name, *map(str, args)]
    runpy.run_path(str(REPO / 'scripts' / name), run_name='__main__')


def load_model(cfg):
    """steering.experiment.load (seed 42, BF16, SDPA) plus the intervention's steering fit."""
    import torch
    from steering import experiment
    model, tokenizer, layers = experiment.load()
    fit = torch.load(repo_path(cfg.intervention.fit), map_location='cpu', weights_only=False)
    return model, tokenizer, layers, fit


def task_infer(cfg, out):
    from steering import experiment
    root, steering_run = run_workspace(cfg)
    bind(root, steering_run)
    if cfg.intervention.name.startswith('cp_'):
        from steering.cp_exploratory import CPReplayHook
        experiment.ResidualSteerer = CPReplayHook  # same substitution as scripts/submission_infer.py
    model, tokenizer, layers, fit = load_model(cfg)
    result, _ = experiment.generate(model, tokenizer, layers, fit, [{'role': 'user', 'content': cfg.task.prompt}],
                                    dict(cfg.intervention.setting), max_new_tokens=cfg.task.max_new_tokens)
    del result['trace']
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(result['text'])


def generate_mask(cfg, steering_run):
    from steering import experiment
    os.environ['STEERING_EVAL_CONDITIONS'] = cfg.intervention.name  # one journal per intervention
    os.environ['MASK_SUBSET_PATH'] = str(repo_path(cfg.dataset.manifest))
    model, tokenizer, layers, fit = load_model(cfg)
    locked = json.loads((steering_run / 'locked_settings.json').read_text())
    experiment.evaluate_mask(model, tokenizer, layers, fit, locked)


def generate_capability(cfg, steering_run):
    from steering import capability
    sys.argv = ['steering.capability', '--condition', cfg.intervention.name]
    capability.main()


def generate_machiavelli(cfg, steering_run):
    from steering import machiavelli_local
    d = cfg.dataset
    sys.argv = ['steering.machiavelli_local', '--condition', cfg.intervention.name, '--output-name', d.output_name,
                '--seeds', ','.join(map(str, d.seeds)), '--game-count', str(d.game_count), '--max-steps', str(d.max_steps)]
    machiavelli_local.main()


# dataset kind -> (library module that owns the run paths, generator)
GENERATORS = {'mask': ('steering.experiment', generate_mask),
              'capability': ('steering.capability', generate_capability),
              'machiavelli': ('steering.machiavelli_local', generate_machiavelli)}


def task_generate(cfg, out):
    assert not cfg.intervention.name.startswith('cp_'), 'CP interventions are exploratory: task=infer only'
    module, generator = GENERATORS[cfg.dataset.kind]
    root, steering_run = run_workspace(cfg)
    importlib.import_module(module)  # import before bind() so its ROOT/RUN globals are redirected
    bind(root, steering_run)
    generator(cfg, steering_run)


def task_judge(cfg, out):
    assert cfg.dataset.kind == 'mask', 'the judge scores MASK generations'
    from steering import grade_pilot
    root, steering_run = run_workspace(cfg)
    bind(root, steering_run)
    manifest = json.loads(repo_path(cfg.dataset.manifest).read_text())['items']
    have = {(r['config'], r['task_id'], r['condition']) for p in steering_run.glob('mask_generations*.jsonl')
            for r in grade_pilot.complete_lines(p) if r['prompt_type'] == 'pressured'}
    missing = [c for c in CONDITIONS if any((i['config'], i['task_id'], c) not in have for i in manifest)]
    if missing:  # grade_pilot waits until all five conditions exist; fail instead of hanging.
        raise RuntimeError(f'generate these interventions first: {missing}')
    os.environ['MASK_JUDGE_FOLDER'] = str(steering_run / 'judge')
    os.environ['MASK_SUBSET_PATH'] = str(repo_path(cfg.dataset.manifest))
    os.environ['MASK_JUDGE_CONCURRENCY'] = str(cfg.judge_model.concurrency)
    asyncio.run(grade_pilot.main_async(Namespace(backend='local', execute_paid=False, smoke_only=False)))


def task_report(cfg, out):
    from honesty import report
    report.fresh_run(cfg, Path(cfg.paths.run))


def task_rebuild(cfg, out):
    from honesty import report
    from scripts import submission_tables
    run = Path(cfg.paths.run)
    package = run / 'package'
    count = materialize_package(cfg.task.evidence_manifest, package, exclude_prefix=cfg.task.frozen)
    print(f'materialized {count} verified evidence files into {package}')
    (package / 'report/figures').mkdir(parents=True)
    submission_tables.main(package)
    run_script('render_submission.py', '--package', package)
    report.rebuild_outputs(cfg, run, package)


def task_audit(cfg, out):
    run_script('verify_mask_evidence.py', '--package', cfg.task.package)


TASKS = {'rebuild': task_rebuild, 'infer': task_infer, 'generate': task_generate,
         'judge': task_judge, 'report': task_report, 'audit': task_audit}


@hydra.main(version_base='1.3', config_path=str(REPO / 'conf'), config_name='config')
def main(cfg):
    out = save_resolved(cfg)
    check_locked(cfg)
    print(f'task={cfg.task.name} run={cfg.paths.run} resolved_config={out / "resolved_config.yaml"}')
    TASKS[cfg.task.name](cfg, out)


if __name__ == '__main__':
    main()
