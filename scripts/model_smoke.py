import json, time
from pathlib import Path
import torch
from huggingface_hub import snapshot_download
root = Path('/lambda/nfs/fs-cand-nov05')
print('Downloading model', flush=True)
path = snapshot_download('Qwen/Qwen3.5-9B', revision='c202236235762e1c871ad0ccb60c8ee5ba337b9a', local_dir=root/'models/Qwen3.5-9B', max_workers=8)
print('Download complete; starting GPU smoke test', flush=True)
from transformers import AutoProcessor, AutoModelForImageTextToText
assert torch.cuda.is_available()
processor = AutoProcessor.from_pretrained(path, local_files_only=True)
model = AutoModelForImageTextToText.from_pretrained(path, dtype=torch.bfloat16, device_map={'':0}, local_files_only=True, attn_implementation='sdpa')
messages = [{'role':'user','content':[{'type':'text','text':'What is 2 + 2? Answer briefly.'}]}]
inputs = processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors='pt', enable_thinking=False).to('cuda:0')
start=time.time()
with torch.inference_mode():
    output=model.generate(**inputs, max_new_tokens=32, do_sample=False)
torch.cuda.synchronize()
answer=processor.batch_decode(output[:,inputs['input_ids'].shape[1]:],skip_special_tokens=True)[0]
assert output.shape[1] > inputs['input_ids'].shape[1]
result={'status':'passed','model':'Qwen/Qwen3.5-9B','revision':'c202236235762e1c871ad0ccb60c8ee5ba337b9a','gpu':torch.cuda.get_device_name(0),'answer':answer,'generation_seconds':time.time()-start,'peak_gpu_bytes':torch.cuda.max_memory_allocated(0)}
(root/'results/gpu_smoke.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2),flush=True)
