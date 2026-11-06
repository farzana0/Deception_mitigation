"""Stream model files and compare with pinned Hugging Face download ETags.

This checks local identity against cached download metadata; authenticate upstream
metadata independently before treating that cache as an independent trust root.
"""
import argparse,datetime,hashlib,json,time
from pathlib import Path
REVISION='c202236235762e1c871ad0ccb60c8ee5ba337b9a'
def verify(root,output):
 records=[]
 index=json.loads((root/'model.safetensors.index.json').read_text())
 shards=sorted(set(index['weight_map'].values()))
 assert len(shards)==4
 for name in shards:
  path=root/name;metadata=(root/'.cache/huggingface/download'/(name+'.metadata')).read_text().splitlines()
  assert metadata[0]==REVISION,(name,'revision mismatch')
  expected=metadata[1];assert len(expected)==64
  before=path.stat();digest=hashlib.sha256();start=time.monotonic()
  with path.open('rb') as f:
   for block in iter(lambda:f.read(8*1024*1024),b''):digest.update(block)
  after=path.stat();actual=digest.hexdigest()
  assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),'file changed during hashing'
  record=dict(file=name,bytes=after.st_size,sha256=actual,expected_cached_etag=expected,passed=actual==expected,seconds=time.monotonic()-start)
  records.append(record);print(json.dumps(record),flush=True)
  result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),revision=REVISION,status='passed' if len(records)==len(shards) and all(r['passed'] for r in records) else 'incomplete_or_failed',trust_scope='Cached pinned Hugging Face download metadata; independent upstream metadata not yet verified',shards=records)
  output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
 assert all(r['passed'] for r in records),'weight hash mismatch'
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--model-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();verify(a.model_dir,a.output)
