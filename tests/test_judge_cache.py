import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from steering.grade_pilot import Transport

class Response:
    def __init__(self,value):self.value=value
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self):return json.dumps(self.value).encode()

class JudgeCacheTests(unittest.TestCase):
    def test_failed_request_is_retried_on_resume_and_success_reused(self):
        official={'extract_boxed_evaluation':lambda text:'A' if text=='Answer: A' else None}
        value={'choices':[{'finish_reason':'stop','message':{'content':'Answer: A'}}]}
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            transport=Transport(folder,'local',official)
            with patch('urllib.request.urlopen',side_effect=OSError('interrupted')),patch('time.sleep'):
                self.assertIsNone(transport.call('test','system',False))
            transport=Transport(folder,'local',official)
            with patch('urllib.request.urlopen',return_value=Response(value)) as request:
                self.assertEqual(transport.call('test','system',False),'Answer: A')
                self.assertEqual(request.call_count,1)
            transport=Transport(folder,'local',official)
            with patch('urllib.request.urlopen',side_effect=AssertionError('should reuse successful cache')):
                self.assertEqual(transport.call('test','system',False),'Answer: A')

if __name__=='__main__':unittest.main()
