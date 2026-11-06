"""Tables, figures, paired prompt/response examples and comparisons with the saved evidence.

MASK table rows come from scripts/submission_tables.py, so every number uses the published
deduplication, pairing and assessability rules.
"""
import csv, filecmp, json, shutil

import matplotlib
import matplotlib.ft2font
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from cais.workspace import CONDITIONS, REPO, jsonl, repo_path, sha256

LABELS = {1: 'honest', -1: 'dishonest', 0: 'not assessable'}
REBUILT_FIGURES = ['mask_main.png'] + [f'page_{i:02d}.png' for i in range(1, 11)]
FULL_COHORT_FIRST_OBSERVED = '2026-11-06T14:43:40.361089+00:00'


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_generations(paths):
    """Generation records keyed by (config, task_id, condition, prompt_type); duplicates must agree."""
    rows = {}
    for path in sorted(paths):
        for r in jsonl(path):
            key = (r['config'], r['task_id'], r['condition'], r['prompt_type'])
            assert key not in rows or rows[key]['result']['token_ids'] == r['result']['token_ids'], f'conflicting generations {key}'
            rows[key] = r
    return rows


def latest_judgments(path):
    return {(r['config'], r['task_id'], r['condition']): r for r in jsonl(path)}


def paired_examples(items, generations, judgments):
    """Per item: the shared pressured prompt and each intervention's response with its judged label."""
    examples = []
    for item in items:
        config, task = item['config'], item['task_id']
        prompt = generations[(config, task, 'baseline', 'pressured')]['messages']
        conditions = {}
        for c in CONDITIONS:
            g, j = generations[(config, task, c, 'pressured')], judgments[(config, task, c)]
            assert g['messages'] == prompt and j['status'] == 'complete'
            scores = j['scoring_inputs']
            conditions[c] = {'response': g['result']['text'], 'truncated': g['result']['hit_token_limit'],
                             'honesty': j['honesty'], 'label': LABELS[j['honesty']], 'pressure_judgment': scores['pressure'],
                             'elicited_belief': scores.get('eval_belief'),  # absent for provided_facts (uses ground truth)
                             'ground_truth': scores['ground_truth_extracted']}
        examples.append({'config': config, 'task_id': task, 'messages': prompt, 'conditions': conditions})
    return examples


def write_examples(examples, folder, title):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'paired_examples.jsonl').write_text(''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in examples))
    lines = [f'# {title}', '',
             'Same pressured MASK prompt, one greedy response per intervention (Qwen/Qwen3.5-9B, seed 42, 256 new tokens).',
             'Labels are from the unsteered local gpt-oss-20b judge with the official MASK rubric.', '']
    for e in examples:
        lines += [f"## {e['config']} / {e['task_id']}", '']
        for m in e['messages']:
            lines += [f"**{m['role']}**", '', '~~~~text', m['content'], '~~~~', '']
        for c, r in e['conditions'].items():
            lines += [f"### {c}: {r['label']} (pressure={r['pressure_judgment']}, belief={r['elicited_belief']}, "
                      f"ground truth={r['ground_truth']}{', truncated' if r['truncated'] else ''})", '',
                      '~~~~text', r['response'], '~~~~', '']
    (folder / 'paired_examples.md').write_text('\n'.join(lines))


def figure_data(rows, series):
    return [{'series': series, 'condition': r['condition'], 'assessable_n': r['assessable_n'],
             'dishonest': r['dishonest'], 'deception_percent': round(100 * r['deception'], 6)} for r in rows]


def bar_figure(path, series, title):
    """Deception rate per condition, styled like the published mask_main.png."""
    fig, ax = plt.subplots(figsize=(8, 4))
    width = 0.8 / len(series)
    for k, ((label, rows), color) in enumerate(zip(series.items(), ['#246b87', '#9bbfcf'])):
        offset = (k - (len(series) - 1) / 2) * width
        ax.bar([i + offset for i in range(len(rows))], [100 * r['deception'] for r in rows], width=width, color=color, label=label)
    ax.set_xticks(range(len(CONDITIONS)), CONDITIONS)
    ax.set_ylabel('Dishonest / assessable (%)')
    ax.set_ylim(0, 100)
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def identical(a, b):
    return filecmp.cmp(a, b, shallow=False)


def rebuild_outputs(cfg, run, package):
    """Paired examples and figure data from the rebuilt package, then compare with results/frozen."""
    frozen = repo_path(cfg.task.frozen)
    steering_run = package / 'experiments/results/steering_run'
    items = json.loads(repo_path(cfg.task.examples_manifest).read_text())['items']
    generations = load_generations(steering_run.glob('mask_generations*.jsonl'))
    examples = paired_examples(items, generations, latest_judgments(package / cfg.task.examples_judgments))
    write_examples(examples, run / 'paired_examples', 'Paired MASK examples (full 1,000-item cohort, 12 fixed items)')
    tables = json.loads((package / 'report/tables/verified_tables.json').read_text())
    write_csv(run / 'figure_data/mask_main.csv', figure_data(tables['mask_full1000'], 'full1000'))
    selection = json.loads((package / 'experiments/cohort_selection.json').read_text())

    checks = {f'tables/{p.name}': identical(package / 'report/tables' / p.name, p) for p in sorted((frozen / 'tables').iterdir())}
    checks['verified_item_ids.json'] = identical(package / 'data/verified_item_ids.json', frozen / 'verified_item_ids.json')
    checks['report.md'] = identical(package / 'report/report.md', frozen / 'report.md')
    frozen_tables = json.loads((frozen / 'tables/verified_tables.json').read_text())
    checks['figure data: mask_main bar heights'] = (
        [(r['condition'], r['deception']) for r in tables['mask_full1000']] ==
        [(r['condition'], r['deception']) for r in frozen_tables['mask_full1000']])
    checks['figure_data/mask_main.csv'] = identical(run / 'figure_data/mask_main.csv', REPO / 'results/figure_data/mask_main.csv')
    # PNG bytes depend on the FreeType build used for text antialiasing, so they are reported, not gated.
    png_identical = {n: identical(package / 'report/figures' / n, frozen / 'figures' / n) for n in REBUILT_FIGURES}
    checks.update({f'paired_examples/{n}': identical(run / 'paired_examples' / n, REPO / 'results/paired_examples' / n)
                   for n in ['paired_examples.jsonl', 'paired_examples.md']})
    checks['cohort selection: full1000, first observed before freeze'] = (
        selection['primary_cohort'] == 'full1000' and selection['full_completion_observed_utc'] == FULL_COHORT_FIRST_OBSERVED)

    outputs = run / 'outputs'
    shutil.rmtree(outputs, ignore_errors=True)
    shutil.copytree(package / 'report', outputs)
    shutil.copy2(package / 'data/verified_item_ids.json', outputs)
    result = {'status': 'passed' if all(checks.values()) else 'failed', 'checks': checks,
              'png_byte_identical': png_identical,
              'renderer': {'matplotlib': matplotlib.__version__, 'freetype': matplotlib.ft2font.__freetype_version__},
              'not_compared': 'report.pdf embeds its creation time', 'outputs': str(outputs)}
    (run / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if result['status'] != 'passed':
        raise SystemExit(f'offline rebuild differs from {frozen}; see {run / "verification.json"}')


def fresh_run(cfg, run):
    """Table, figure, examples and exact comparison with saved evidence for a fresh MASK run."""
    from scripts.submission_tables import audit
    steering_run, report = run / 'steering_run', run / 'report'
    report.mkdir(parents=True, exist_ok=True)
    manifest = repo_path(cfg.dataset.manifest)
    items = json.loads(manifest.read_text())['items']
    keys = {(i['config'], i['task_id']) for i in items}

    # Saved judgments for the same items, written as a journal so audit() treats both identically.
    saved_judgments = {k: r for k, r in latest_judgments(repo_path(cfg.task.compare_judgments_with)).items() if k[:2] in keys}
    reference = report / 'saved_judgments_subset.jsonl'
    reference.write_text(''.join(json.dumps(r) + '\n' for r in saved_judgments.values()))
    fresh_rows, _ = audit(steering_run / 'judge/items.jsonl', manifest, CONDITIONS)
    saved_rows, _ = audit(reference, manifest, CONDITIONS)
    write_csv(report / 'mask_table.csv', fresh_rows)
    write_csv(report / 'mask_table_saved_evidence.csv', saved_rows)
    write_csv(report / 'figure_data.csv', figure_data(fresh_rows, 'fresh') + figure_data(saved_rows, 'saved'))
    bar_figure(report / 'mask_deception.png', {'fresh rerun': fresh_rows, 'saved evidence': saved_rows},
               f'MASK {cfg.dataset.name}: {len(items)} matched items')

    fresh = {k: v for k, v in load_generations(steering_run.glob('mask_generations*.jsonl')).items() if k[:2] in keys}
    saved = load_generations(repo_path(cfg.task.compare_generations_with).glob('mask_generations*.jsonl.gz'))
    fresh_judgments = latest_judgments(steering_run / 'judge/items.jsonl')
    assert all(v['status'] == 'complete' for v in fresh_judgments.values()), 'judge failures remain; rerun task=judge'
    token_mismatches = [list(k) for k, v in fresh.items() if v['result']['token_ids'] != saved[k]['result']['token_ids']]
    label_mismatches = [{'item': list(k), 'fresh': v['honesty'], 'saved': saved_judgments[k]['honesty']}
                        for k, v in fresh_judgments.items() if v['honesty'] != saved_judgments[k]['honesty']]
    write_examples(paired_examples(items, fresh, fresh_judgments), report, f'Paired MASK examples, fresh rerun of {cfg.dataset.name}')
    comparison = {'generations': len(fresh), 'generations_token_identical': len(fresh) - len(token_mismatches),
                  'token_mismatches': token_mismatches, 'judged_condition_items': len(fresh_judgments),
                  'honesty_labels_identical': len(fresh_judgments) - len(label_mismatches), 'label_mismatches': label_mismatches,
                  'table_identical_to_saved_evidence': fresh_rows == saved_rows,
                  'judge_calls_sha256': sha256(steering_run / 'judge/calls.jsonl')}
    (report / 'comparison.json').write_text(json.dumps(comparison, indent=2) + '\n')
    print(json.dumps(comparison, indent=2))
