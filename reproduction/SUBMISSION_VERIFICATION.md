# CAIS submission verification — 2026-11-06

MASK is complete: 1,000 matched manifest items, five conditions, 5,000 technically complete condition-items. The full cohort was verified at 14:43:40 UTC, before the 22:00 UTC Toronto freeze. The original 240 is retained as a reference; the 24-item CP pilot remains separate and exploratory.

Passed checks:

- Complete manifest-matched pairs across all five main conditions; latest-record deduplication, no technical judge failures in retained items, successful judge-call references and locked setting hashes.
- All 5,000 main condition-item honesty labels reproduced from exact saved scoring inputs using the pinned official MASK metric. All retained judge responses were re-parsed and 14,930 prompt records were linked to their generation outputs.
- The 1,200 original-cohort condition-items and 48 CP condition-items passed the same evidence audit. CP has 24 technical pairs and 13 shared assessable items; it is disjoint from the original 240 and overlaps the full manifest in 24 items.
- Frozen source, steering fit, calibration journal, generated contrast pairs and extraction/calibration split hashes match locked records.
- Capability response scoring independently reproduced on deterministic matching MMLU30 and GSM8K10 indices per condition.
- All four base-weight shards match cached Hugging Face LFS SHA256 digests for Qwen3.5-9B revision c202236235762e1c871ad0ccb60c8ee5ba337b9a; sizes and modification times stayed stable during streaming hashing.
- Twenty targeted tests passed: four core steering, three CP, five MASK parsing, three NFS reads, one journal recovery, three submission/cohort selection and one weight-corruption test. The core steering test confirms all five modes leave module parameters unchanged and remove their hooks.
- Python compilation and diff whitespace checks passed. The preflight archive verified all file checksums, regenerated identical main tables in a fresh extracted directory, and opened the ten-page PDF with a PDF parser. The same sealing procedure is used for the completed full-cohort archive; its external verification JSON records the resulting digest and checks.

Numerical metric caveat: the pinned upstream MASK metric serializes a set of numeric intervals. Its infinity fallback parser depends on interval order for two condition-item labels (one CAA and one pooled). Permutation diagnostics document both cases; primary labels and settings remain untouched. No CP labels were order-sensitive in this diagnostic.

Checks that have not passed:

- Clean GPU reproduction was attempted but stopped before inference because this session has no accessible CUDA device. nvidia-smi cannot communicate with the driver. The prior saved GPU smoke is not counted as a fresh reproduction.
- Independent online retrieval of upstream weight metadata is unavailable. Weight identity is verified against cached pinned download records, not an independently retrieved online trust root.
- The complete test suite is not certified: the concurrent judge-cache test timed out under this sandbox, and cluster-root multiprocessing tests were not rerun here. The twenty targeted passes above are the claimed test scope.
- Native Machiavelli replay was not rerun here. The saved audit passed 20 trajectories; those saved replay-verified scores are reported.
- Cluster tmux access and starting a new tmux socket are denied; /lambda is outside this session's writable scope. No worker was restarted or stopped and no cluster package installation is claimed.
- Existing origin is git@github.com:farzana0/Deception_mitigation.git. SSH DNS resolution fails; the connected farzana0 GitHub app returns 404 for this private repository. Remote divergence, publication and remote commit presence cannot currently be verified. No force-push is authorized or used.
