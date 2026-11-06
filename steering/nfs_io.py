"""Bounded retries for transient NFS reads; never substitute missing scientific data."""
import errno,json,time
from pathlib import Path
TRANSIENT={errno.ESTALE,errno.EIO,errno.EINTR,errno.EAGAIN}
def read_text(path,attempts=8):
    path=Path(path)
    for attempt in range(attempts):
        try:return path.read_text()
        except OSError as error:
            if error.errno not in TRANSIENT or attempt+1==attempts:raise
            time.sleep(min(.05*2**attempt,.5))
def read_json(path):return json.loads(read_text(path))
