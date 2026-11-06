"""Recover an interrupted final JSONL append; one writer per journal is required."""
import hashlib

def repair_tail(path):
    if not path.exists():return
    with path.open('rb+') as stream:
        data=stream.read()
        if not data or data.endswith(b'\n'):return
        boundary=data.rfind(b'\n')+1;tail=data[boundary:]
        recovery=path.with_name(path.name+'.interrupted-tail-'+hashlib.sha256(tail).hexdigest()[:12])
        if not recovery.exists():recovery.write_bytes(tail)
        stream.seek(boundary);stream.truncate();stream.flush()
