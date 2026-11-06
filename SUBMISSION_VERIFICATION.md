# Provisional package verification

- Saved-evidence audit passed: MASK original 240 complete paired items; expansion snapshot 819/1000 complete pairs; CP 24 complete pairs, disjoint from the original 240.
- Main settings digest and fitted intervention digest match the locked values.
- Capability scores independently re-extracted from saved response text on matched MMLU30 and GSM8K10 items per condition.
- Fresh-directory table regeneration produced identical verified_tables.json.
- Portable workspace materialization succeeded in a fresh /tmp directory.
- Three existing core steering tests, three existing CP tests (with the recorded cluster deps on PYTHONPATH), and two new submission audit tests passed.
- PDF is a nine-page PDF 1.4 document; rendered page previews were visually inspected. A PDF-reading renderer was unavailable in this environment.
- Python packaging scripts compile; staged diff whitespace check passed.
- Initial CP test import without the cluster deps path failed because system Pillow lacks Image.Resampling. Use the recorded cluster PYTHONPATH/dependency environment. Full test suite was interrupted after the concurrent judge-cache test stalled; no full-suite pass is claimed.
- GPU inference, clean dependency installation, native Machiavelli replay and independent upstream base-weight byte comparison were not performed here.
- Existing origin matches git@github.com:farzana0/Deception_mitigation.git. Git remote query/push failed DNS resolution; branch divergence and remote commit presence could not be verified.
- Cluster tmux access is denied and /lambda is read-only under this session's permissions. No live-worker health conclusion, worker restart, cluster freeze or cluster installation is claimed.
