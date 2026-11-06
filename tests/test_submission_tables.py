import datetime,json,tempfile,unittest
from pathlib import Path
from scripts.submission_tables import audit,select_cohort,FREEZE
class SubmissionTablesTests(unittest.TestCase):
 def test_full_cohort_must_be_observed_by_freeze(self):
  before=FREEZE-datetime.timedelta(seconds=1);after=FREEZE+datetime.timedelta(seconds=1)
  self.assertEqual(select_cohort(1000,before),'full1000')
  self.assertEqual(select_cohort(1000,FREEZE),'full1000')
  self.assertEqual(select_cohort(999,before),'original240')
  self.assertEqual(select_cohort(1000,after),'original240')
  self.assertEqual(select_cohort(1000,after,before),'full1000')
  self.assertEqual(select_cohort(999,after,before),'original240')
 def test_latest_failure_removes_pair_and_unknown_is_not_technical_failure(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);manifest=root/'manifest.json';journal=root/'items.jsonl'
   manifest.write_text(json.dumps({'items':[{'config':'x','task_id':'1'},{'config':'x','task_id':'2'}]}))
   rows=[dict(config='x',task_id=i,condition=c,status='complete',judge_failures=[],honesty=-1 if c=='base' else 0) for i in ['1','2'] for c in ['base','steer']]
   rows.append(dict(config='x',task_id='2',condition='steer',status='failed',judge_failures=['interrupted']))
   journal.write_text(''.join(json.dumps(r)+'\n' for r in rows)+'{"partial":')
   table,ids=audit(journal,manifest,['base','steer'])
   self.assertEqual(ids,{('x','1')});self.assertEqual(table[1]['complete_paired_n'],1);self.assertEqual(table[1]['assessable_n'],0);self.assertIsNone(table[1]['paired_delta'])
 def test_duplicate_manifest_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);m=root/'manifest.json';j=root/'items.jsonl';j.write_text('');m.write_text(json.dumps({'items':[{'config':'x','task_id':'1'}]*2}))
   with self.assertRaises(AssertionError):audit(j,m,['base','steer'])
if __name__=='__main__':unittest.main()
