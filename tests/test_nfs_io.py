import errno,json,unittest
from pathlib import Path
from unittest.mock import patch
from steering.nfs_io import read_text,read_json
class NfsReadTests(unittest.TestCase):
    def test_stale_replaced_file_reopens_and_returns_complete_data(self):
        with patch.object(Path,'read_text',side_effect=[OSError(errno.ESTALE,'stale'),OSError(errno.ESTALE,'stale'),'{"paired":421}']) as read,patch('steering.nfs_io.time.sleep'):
            self.assertEqual(read_json('summary.json'),{'paired':421});self.assertEqual(read.call_count,3)
    def test_permission_and_corrupt_json_are_not_replaced_with_default_scores(self):
        with patch.object(Path,'read_text',side_effect=PermissionError(errno.EACCES,'denied')) as read:
            with self.assertRaises(PermissionError):read_text('summary.json')
            self.assertEqual(read.call_count,1)
        with patch.object(Path,'read_text',return_value='{bad'):
            with self.assertRaises(json.JSONDecodeError):read_json('summary.json')
    def test_persistent_stale_handle_is_a_visible_failure(self):
        with patch.object(Path,'read_text',side_effect=OSError(errno.ESTALE,'stale')) as read,patch('steering.nfs_io.time.sleep'):
            with self.assertRaises(OSError):read_text('summary.json',attempts=3)
            self.assertEqual(read.call_count,3)
if __name__=='__main__':unittest.main()
