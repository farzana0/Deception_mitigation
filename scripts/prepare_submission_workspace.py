"""Materialize a portable workspace while preserving original evidence bytes."""
import argparse,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args();src=a.package.resolve();dst=a.destination.resolve()
assert not dst.exists(),'Use a fresh destination'
dst.mkdir(parents=True)
for name,origin in [('Deception_mitigation','experiments/code'),('results','experiments/results'),('data','data'),('repos','experiments/upstream')]:shutil.copytree(src/origin,dst/name)
for path in (dst/'Deception_mitigation').rglob('*'):
 if path.suffix in ['.py','.sh']:
  content=path.read_text();path.write_text(content.replace('/lambda/nfs/fs-cand-nov05',str(dst)))
print(dst)
