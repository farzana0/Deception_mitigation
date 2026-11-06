Next-stage evaluation checkpoint — 2026-11-06T09:36:10.831980+00:00

This is a live next-stage report. The initial overnight report remains a frozen checkpoint. Local GPT-OSS judges use pinned official MASK rubric/aggregation; scores are not official API scores. No paid calls and no steering retuning.

Full MASK: 255/1000 items judged across all five conditions.

| Condition | Judged items | Assessable N | Dishonest | Deception | Undetermined | Truncated pressure | Mean tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 257 | 184 | 96 | 52.174% | 71 | 100 | 171.1 |
| caa | 257 | 186 | 90 | 48.387% | 69 | 85 | 163.8 |
| sttp | 256 | 192 | 102 | 53.125% | 63 | 91 | 166.8 |
| rank2 | 255 | 192 | 97 | 50.521% | 63 | 95 | 170.3 |
| pooled | 260 | 186 | 98 | 52.688% | 69 | 91 | 166.8 |

Deception uses dishonest/(honest+dishonest); unknown labels remain in the all-paired denominator, reported in metrics. Partial generated-pressure token counts above may cover more items than the judged common set. Technical failures remain separate. See next_stage_metrics.json for strata, fixed-baseline-belief sensitivity, common assessability, rank2/pooled discordances and perturbation telemetry.

Auxiliary quality_mask_v1: 78 primary comparisons; 19 items common to all four comparisons; 0 technical failures.

| Condition | Common N | Utility delta (steered minus baseline) | 95% paired bootstrap interval |
| --- | ---: | ---: | --- |
| caa | 19 | 0.10526315789473684 | [-0.21052631578947367, 0.42105263157894735] |
| sttp | 19 | -0.05263157894736842 | [-0.3684210526315789, 0.3157894736842105] |
| rank2 | 19 | -0.3684210526315789 | [-0.6842105263157895, -0.10526315789473684] |
| pooled | 19 | -0.21052631578947367 | [-0.5789473684210527, 0.15789473684210525] |

All deception-reduction/quality-loss cases: 0, including dishonest-to-undetermined transitions flagged separately. Full quotes and IDs: /lambda/nfs/fs-cand-nov05/results/steering_run/quality_mask_v1/deception_improvement_quality_loss_cases.json.
Order-swap checks: 4; utility-delta disagreements: 1.
Rank2 versus pooled: {"steered_utility_difference": {"n": 19, "mean": -0.10526315789473684, "ci95": [-0.42105263157894735, 0.21052631578947367], "method": "paired item bootstrap, 2000 resamples, seed42; diagnostic, no multiplicity correction"}, "paired_quality_delta_difference": {"n": 19, "mean": -0.15789473684210525, "ci95": [-0.6855263157894737, 0.3684210526315789], "method": "paired item bootstrap, 2000 resamples, seed42; diagnostic, no multiplicity correction"}, "note": "Separate blinded comparisons may rate the same baseline differently; per-pair deltas and swapped-order checks expose judge variation."}

Auxiliary quality_capability_v2: 88 primary comparisons; 22 items common to all four comparisons; 0 technical failures.

| Condition | Common N | Utility delta (steered minus baseline) | 95% paired bootstrap interval |
| --- | ---: | ---: | --- |
| caa | 22 | 0.0 | [0.0, 0.0] |
| sttp | 22 | 0.09090909090909091 | [0.0, 0.22727272727272727] |
| rank2 | 22 | 0.0 | [0.0, 0.0] |
| pooled | 22 | -0.13636363636363635 | [-0.5454545454545454, 0.13636363636363635] |

All deception-reduction/quality-loss cases: 0, including dishonest-to-undetermined transitions flagged separately. Full quotes and IDs: /lambda/nfs/fs-cand-nov05/results/steering_run/quality_capability_v2/deception_improvement_quality_loss_cases.json.
Order-swap checks: 0; utility-delta disagreements: 0.
Rank2 versus pooled: {"steered_utility_difference": {"n": 22, "mean": 0.0, "ci95": [0.0, 0.0], "method": "paired item bootstrap, 2000 resamples, seed42; diagnostic, no multiplicity correction"}, "paired_quality_delta_difference": {"n": 22, "mean": 0.13636363636363635, "ci95": [-0.13636363636363635, 0.5454545454545454], "method": "paired item bootstrap, 2000 resamples, seed42; diagnostic, no multiplicity correction"}, "note": "Separate blinded comparisons may rate the same baseline differently; per-pair deltas and swapped-order checks expose judge variation."}

Matched apparent-deception-reduction diagnostics: {"caa": {"count": 18, "became_undetermined": 6, "became_honest": 12, "status_judged": 18, "steered_explicit_refusal": 2, "steered_epistemic_abstention": 0, "quality_judged": 0, "worse_utility": 0}, "sttp": {"count": 12, "became_undetermined": 8, "became_honest": 4, "status_judged": 12, "steered_explicit_refusal": 2, "steered_epistemic_abstention": 0, "quality_judged": 1, "worse_utility": 0}, "rank2": {"count": 13, "became_undetermined": 4, "became_honest": 9, "status_judged": 13, "steered_explicit_refusal": 2, "steered_epistemic_abstention": 0, "quality_judged": 0, "worse_utility": 0}, "pooled": {"count": 16, "became_undetermined": 7, "became_honest": 9, "status_judged": 16, "steered_explicit_refusal": 4, "steered_epistemic_abstention": 0, "quality_judged": 0, "worse_utility": 0}}

All matched labels, token lengths, truncations, response status and quality scores are preserved in next_stage_matched_items.json. Capability paired accuracy differences and uncertainty are in next_stage_metrics.json (capability_matched_changes).

Quality margins (0.25 utility points; 5 capability percentage points) are diagnostic, not evidence of equivalence. Bootstrap intervals describe variation across these fixed items under this judge; they exclude model/judge uncertainty. Capability N=30 MMLU and N=10 GSM8K, game/seed N=4, are small. Quality preservation must remain inconclusive unless intervals support the diagnostic margin. Apparent deception reductions through undetermined answers, refusal, uncertainty or worse utility are not unqualified successes.

Capability: deterministic accuracy is primary; auxiliary extraction reads only explicit saved final answers.

| Benchmark | Condition | N | Original correct | Assisted correct | Rescues | Judge failures | Truncated |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| mmlu | baseline | 30 | 21 | 21 | 0 | 0 | 0 |
| mmlu | caa | 30 | 21 | 21 | 0 | 0 | 0 |
| mmlu | sttp | 30 | 21 | 21 | 0 | 0 | 0 |
| mmlu | rank2 | 30 | 21 | 21 | 0 | 0 | 0 |
| mmlu | pooled | 30 | 20 | 20 | 0 | 0 | 0 |
| gsm8k | baseline | 10 | 8 | 9 | 1 | 0 | 2 |
| gsm8k | caa | 10 | 8 | 10 | 2 | 0 | 2 |
| gsm8k | sttp | 10 | 8 | 9 | 1 | 0 | 2 |
| gsm8k | rank2 | 10 | 9 | 10 | 1 | 0 | 1 |
| gsm8k | pooled | 10 | 10 | 10 | 0 | 0 | 0 |

Refusal/uncertainty auxiliary coverage: 256/1000 common items. Full condition counts: {"baseline": {"paired_denominator": 256, "complete_items": 258, "explicit_refusal_count": 69, "epistemic_abstention_count": 1, "overlap_count": 0, "technical_item_failures": 0}, "caa": {"paired_denominator": 256, "complete_items": 258, "explicit_refusal_count": 69, "epistemic_abstention_count": 1, "overlap_count": 1, "technical_item_failures": 0}, "sttp": {"paired_denominator": 256, "complete_items": 257, "explicit_refusal_count": 66, "epistemic_abstention_count": 0, "overlap_count": 0, "technical_item_failures": 0}, "rank2": {"paired_denominator": 256, "complete_items": 256, "explicit_refusal_count": 66, "epistemic_abstention_count": 2, "overlap_count": 1, "technical_item_failures": 0}, "pooled": {"paired_denominator": 256, "complete_items": 261, "explicit_refusal_count": 66, "epistemic_abstention_count": 0, "overlap_count": 0, "technical_item_failures": 0}}

Machiavelli native replay: 20/20 main trajectories. Auxiliary decision audit: 81 completed annotations. All saved trajectory inventory: /lambda/nfs/fs-cand-nov05/results/steering_run/machiavelli_quality_v1/inventory.json; all invalid attempts: /lambda/nfs/fs-cand-nov05/results/steering_run/machiavelli_quality_v1/all_invalid_attempts.json.

| Condition | Main paired trajectories | Official deception | Official saved points | Final replay points | Random fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 4 | 71.690 | 6.897 | 6.897 | 26 |
| caa | 4 | 77.034 | 14.298 | 18.608 | 12 |
| sttp | 4 | 96.846 | 10.121 | 12.995 | 23 |
| rank2 | 4 | 93.392 | 8.653 | 11.526 | 16 |
| pooled | 4 | 111.206 | 14.649 | 19.885 | 43 |

Machiavelli states diverge across conditions. Only game/seed trajectories are paired; on-policy steps are not identical-state comparisons. Smoke/replay-validation outputs are audited separately and excluded from main scores.

Live jobs:
```
deception-next: 1 windows (created Fri Nov  6 09:23:12 2026)
deception-next-watchdog: 1 windows (created Fri Nov  6 09:23:47 2026)
machiavelli-fixed-states: 1 windows (created Fri Nov  6 09:33:44 2026)
machiavelli-quality: 1 windows (created Fri Nov  6 09:27:55 2026)
mask-full-baseline: 1 windows (created Fri Nov  6 09:20:41 2026)
mask-full-caa: 1 windows (created Fri Nov  6 09:20:41 2026)
mask-full-judge: 1 windows (created Fri Nov  6 09:30:49 2026)
mask-full-pooled: 1 windows (created Fri Nov  6 09:20:41 2026)
mask-full-rank2: 1 windows (created Fri Nov  6 09:20:41 2026)
mask-full-sttp: 1 windows (created Fri Nov  6 09:20:41 2026)
mask-judge-server: 1 windows (created Fri Nov  6 02:58:32 2026)
quality-capability: 1 windows (created Fri Nov  6 09:28:09 2026)
quality-mask: 1 windows (created Fri Nov  6 09:25:46 2026)
response-status-full: 1 windows (created Fri Nov  6 09:29:25 2026)
```

Remaining work/blockers: full judging, quality and auxiliary coverage must reach their declared targets and pass saved-output validation before completion is asserted. Inspect per-worker logs for failures; generation/judging may have different coverage. The server remains healthy unless health/log checks show otherwise. Safety cutoff: 2026-11-07T03:00:00Z.

Exact resume commands are in NEXT_STAGE_REPRODUCIBILITY.md and NEXT_STAGE_RESUME.sh. Inspect sessions/PIDs first; never duplicate a writer. Primary scores: results/steering_run/judge_gptoss_full. Completion manifest is written only by the final validator.
