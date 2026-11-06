import hashlib,json,tempfile,unittest
from pathlib import Path
from scripts.verify_base_weights import verify,REVISION
class BaseWeightTests(unittest.TestCase):
 def test_matching_shards_pass_and_changed_shard_fails(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);meta=root/'.cache/huggingface/download';meta.mkdir(parents=True);mapping={}
   for i in range(4):
    name=f'shard{i}.safetensors';data=bytes([i]);(root/name).write_bytes(data);(meta/(name+'.metadata')).write_text(REVISION+'\n'+hashlib.sha256(data).hexdigest()+'\n0\n');mapping[str(i)]=name
   (root/'model.safetensors.index.json').write_text(json.dumps({'weight_map':mapping}))
   result=verify(root,root/'verified.json');self.assertEqual(result['status'],'passed')
   (root/'shard1.safetensors').write_bytes(b'changed')
   with self.assertRaisesRegex(AssertionError,'weight hash mismatch'):verify(root,root/'verified.json')
   self.assertEqual(json.loads((root/'verified.json').read_text())['status'],'incomplete_or_failed')
if __name__=='__main__':unittest.main()
