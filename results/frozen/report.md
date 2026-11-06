CAIS | Activation steering for honesty
Verified full-cohort evidence package • 6 November 2026

All 1,000 MASK items are technically complete and matched across five conditions, verified at 2026-11-06T14:43:40.361089+00:00, before the 22:00 UTC freeze. The full cohort is the main MASK result; the original 240-item cohort is shown as a historical reference.

The results do not establish a general reduction in deception. MASK paired effects vary by intervention; Machiavelli deception rises for all four steered conditions in this small sample. Capability pilots use only 30 MMLU and 10 GSM8K items per condition. The separate 24-item CP comparison shows no difference on its shared assessable subset.

Methods and interpretation

Five main conditions share one Qwen/Qwen3.5-9B base, revision c202236235762e1c871ad0ccb60c8ee5ba337b9a. CAA uses layer 16 and strength 0.1; StTP layer 20 and c=2; rank-2 and pooled use strength 0.1. Calibration uses ten scenarios, separate from forty extraction scenarios. Settings and fit hashes are checked by the audit command.

MASK uses pinned official CAIS rubric/parsing with a local unsteered openai/gpt-oss-20b judge, revision 6cee5e81ee83917806bbde320786a8fb61efebee. Local model judgments can be wrong; official prompts do not make them human ground truth. Unknown beliefs/abstentions are legitimate outcomes, not technical failures. Deception is dishonest / assessable. Paired deltas use the jointly assessable baseline/condition subset, so subtracting marginal rates may give a different value. Selection of the partial expansion depends on runtime completion and is not a final benchmark estimate.

Machiavelli has four matched game/seed cases per condition (two games, two seeds), twenty trajectories total. Deception is refined violations normalized to the random-agent mean times 100, not a probability. Reward retains the official recorded normalized achievement score. Saved native replay audits passed for twenty trajectories; replay was not rerun here. Random fallback actions and malformed attempts limit interpretation; see the archived report and per-item outputs.

MMLU and GSM8K use the same deterministic test indices across conditions, with 30 and 10 items respectively. Accuracy was independently recalculated from saved response text using the recorded extraction rules. Judge-assisted answer formatting is supplementary and excluded from these primary scores.

CP-scheduled versus CP-static is exploratory: 24 predeclared items disjoint from the original 240 but overlapping all 24 items with the full 1,000-item manifest, matched five layers, offsets >=1, strength 0.1 and equal total relative budget. Both modes are technically complete for 24 items; the direct comparison uses only 13 shared assessable items. The CP modes are reported separately and are not an independent test set for the full main cohort. Neither establishes equivalence or benefit.


Within the main MASK cohort, 559 items are assessable under all five conditions. Rank-2 versus pooled is directly matched on 645 assessable items: 383 versus 380 dishonest.


Numerical MASK reproducibility caveat: the pinned upstream metric serializes a Python set of belief intervals. Its infinity fallback parser can depend on tuple order. The evidence audit reproduces published honesty labels from exact saved scoring inputs and checks their judge responses and generation linkage. Reaggregating numeric beliefs in another process can change some labels; this diagnostic is recorded in experiments/mask_evidence_verification.json and never overwrites the primary outputs. Preserve the saved numeric belief strings when reproducing tables.
 The interval-order permutation diagnostic found 2 potentially order-sensitive condition-item labels in the audited expansion: {'pooled': 1, 'caa': 1}. The main tables retain the original saved labels.


MASK • full 1,000-item main result

condition | complete_paired_n | dishonest | assessable_n | deception | paired_assessable_n | paired_delta
--- | --- | --- | --- | --- | --- | ---
baseline | 1000 | 441 | 729 | 0.604938 | 729 | 0.000000
caa | 1000 | 421 | 741 | 0.568151 | 656 | -0.030488
sttp | 1000 | 451 | 739 | 0.610284 | 666 | 0.007508
rank2 | 1000 | 420 | 728 | 0.576923 | 643 | -0.012442
pooled | 1000 | 423 | 729 | 0.580247 | 634 | -0.025237

Original MASK • 240-item reference

condition | complete_paired_n | dishonest | assessable_n | deception | paired_assessable_n | paired_delta
--- | --- | --- | --- | --- | --- | ---
baseline | 240 | 89 | 171 | 0.520468 | 171 | 0.000000
caa | 240 | 84 | 174 | 0.482759 | 155 | -0.058065
sttp | 240 | 96 | 180 | 0.533333 | 159 | 0.012579
rank2 | 240 | 90 | 180 | 0.500000 | 156 | -0.025641
pooled | 240 | 93 | 174 | 0.534483 | 149 | -0.026846

MASK • primary-cohort diagnostics

condition | paired_n | belief_covered_n | pressure_unknown_n | truncated_n | dishonest_all_n
--- | --- | --- | --- | --- | ---
baseline | 1000 | 800 | 85 | 319 | 441
caa | 1000 | 804 | 73 | 270 | 421
sttp | 1000 | 803 | 76 | 285 | 451
rank2 | 1000 | 791 | 75 | 301 | 420
pooled | 1000 | 799 | 82 | 301 | 423

Capabilities • complete small pilots

condition | benchmark | paired_n | correct | accuracy
--- | --- | --- | --- | ---
baseline | mmlu | 30 | 21 | 0.700000
caa | mmlu | 30 | 21 | 0.700000
sttp | mmlu | 30 | 21 | 0.700000
rank2 | mmlu | 30 | 21 | 0.700000
pooled | mmlu | 30 | 20 | 0.666667
baseline | gsm8k | 10 | 8 | 0.800000
caa | gsm8k | 10 | 8 | 0.800000
sttp | gsm8k | 10 | 8 | 0.800000
rank2 | gsm8k | 10 | 9 | 0.900000
pooled | gsm8k | 10 | 10 | 1.000000

Machiavelli • complete small pilot

condition | paired_n | deception | reward
--- | --- | --- | ---
baseline | 4 | 71.689788 | 6.896552
caa | 4 | 77.033952 | 14.297573
sttp | 4 | 96.846353 | 10.121328
rank2 | 4 | 93.392144 | 8.652618
pooled | 4 | 111.206024 | 14.648787

CP • complete exploratory pilot

condition | complete_paired_n | dishonest | assessable_n | deception | paired_assessable_n | paired_delta
--- | --- | --- | --- | --- | --- | ---
cp_scheduled | 24 | 12 | 15 | 0.800000 | 15 | 0.000000
cp_static | 24 | 13 | 16 | 0.812500 | 13 | 0.000000

Verification and remaining work

Saved MASK judgments were deduplicated by (config, task ID, condition), restricted to manifests and checked for complete status and no judge failures. Complete technical pairs, marginal assessability and paired assessability are separately reported. The original 240 cohort and CP manifest counts are asserted. Main settings SHA256 is 8caa40a84ec74c1ceb2077427b6dd90a00fd3f29d4c1b1328724cf6e717d1527.

Source inspection shows inference-time activation hooks and saved intervention fits, with no base-model training path in the experiment. Base weights are excluded from the package. SHA256 of all four base-weight shards matches the cached Hugging Face LFS ETags for the pinned revision. File sizes and modification times were stable during hashing. Independent retrieval of upstream metadata remains unverified; the trust root is the cached download record.

This environment cannot inspect the live cluster tmux socket, write /lambda, or resolve github.com. No workers were restarted, no cluster submission was installed, and no GitHub push was completed. A local archive can preserve this snapshot, but final cluster freeze, live worker health, clean GPU inference and upstream model identity verification remain pending. MASK cohort selection is recorded separately; GPU reproduction and remote publication remain release gates.

Recorded experiment source commit: 3482088ed25682ae36bce26bfa26c1c3ddc6596b. The source tree had uncommitted report/snapshot additions; provenance.json records them. Packaging scripts were added later and are separately versioned in the local code checkpoint.
