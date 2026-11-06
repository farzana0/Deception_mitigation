import json,tempfile,unittest
from pathlib import Path
from steering.journal import repair_tail
from steering.official_mask import complete_lines

class JournalTests(unittest.TestCase):
    def test_interrupted_append_preserves_complete_rows_and_archives_tail(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'items.jsonl';path.write_bytes(b'{"complete":1}\n{"partial":')
            self.assertEqual(complete_lines(path),[{'complete':1}])
            repair_tail(path)
            with path.open('a') as f:f.write(json.dumps({'resumed':2})+'\n')
            self.assertEqual(complete_lines(path),[{'complete':1},{'resumed':2}])
            archived=list(path.parent.glob('*.interrupted-tail-*'))
            self.assertEqual(len(archived),1);self.assertEqual(archived[0].read_bytes(),b'{"partial":')
            repair_tail(path);self.assertEqual(len(list(path.parent.glob('*.interrupted-tail-*'))),1)
if __name__=='__main__':unittest.main()
