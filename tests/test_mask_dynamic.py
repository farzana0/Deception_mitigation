import json,multiprocessing,tempfile,time,unittest
from pathlib import Path
from steering.mask_dynamic import JournalIndex,Lease,RUN

def claim(folder,queue):
    lease=Lease(Path(folder),('config','item','rank2','pressured'));ok=lease.acquire();queue.put(ok)
    if ok:time.sleep(.25);lease.release()

class DynamicMaskTests(unittest.TestCase):
    def test_cross_process_lease_excludes_overlapping_worker(self):
        with tempfile.TemporaryDirectory(dir=RUN) as folder:
            lease=Lease(Path(folder),('config','item','rank2','pressured'));self.assertTrue(lease.acquire())
            context=multiprocessing.get_context('spawn');queue=context.Queue();process=context.Process(target=claim,args=(folder,queue));process.start();self.assertFalse(queue.get(timeout=20));process.join(timeout=20);self.assertEqual(process.exitcode,0);lease.release()
            process=context.Process(target=claim,args=(folder,queue));process.start();self.assertTrue(queue.get(timeout=20));process.join(timeout=20);self.assertEqual(process.exitcode,0)
    def test_incremental_reader_waits_for_partial_tail_and_sees_other_journal(self):
        with tempfile.TemporaryDirectory(dir=RUN) as folder:
            folder=Path(folder);path=folder/'mask_generations_rank2.jsonl';row={'config':'config','task_id':'item','condition':'rank2','prompt_type':'pressured','messages':[],'result':{'token_ids':[1]}}
            text=json.dumps(row);path.write_text(text[:20]);index=JournalIndex(folder);self.assertEqual(len(index.refresh()),0)
            with path.open('a') as f:f.write(text[20:]+'\n')
            self.assertEqual(len(index.refresh()),1)
            row['condition']='pooled';(folder/'mask_generations_gpu7_helper.jsonl').write_text(json.dumps(row)+'\n');self.assertEqual(len(index.refresh()),2)
if __name__=='__main__':unittest.main()
