import asyncio,json,tempfile,time,unittest
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

class ConcurrentCallTests(unittest.TestCase):
    def test_call_tracking_is_task_local_and_duplicate_payload_is_cached(self):
        official={'extract_boxed_evaluation':lambda text:'A'}
        value={'choices':[{'finish_reason':'stop','message':{'content':'Answer: A'}}]}
        with tempfile.TemporaryDirectory() as directory:
            transport=Transport(Path(directory),'local',official)
            def response(*args,**kwargs):
                time.sleep(.02)
                return Response(value)
            async def task(prompt):
                transport.current=[]
                await asyncio.to_thread(transport.call,prompt,'system',False)
                return [(r['request']['messages'][-1]['content'],r['request_id']) for r in transport.current]
            async def run():return await asyncio.gather(task('first'),task('second'),task('first'))
            with patch('urllib.request.urlopen',side_effect=response) as request:
                results=asyncio.run(run())
            self.assertEqual([[p for p,rid in result] for result in results],[['first'],['second'],['first']])
            self.assertEqual(request.call_count,2)
            self.assertEqual(results[0],results[2])
            self.assertEqual(len(transport.path.read_text().splitlines()),2)

if __name__=='__main__':unittest.main()
