import hashlib,json,random
from pathlib import Path
import torch
from transformers import AutoProcessor,AutoModelForImageTextToText
r=Path('/lambda/nfs/fs-cand-nov05')
source=r/'repos/activation-steering-4-honesty/data/honesty/CAA/self_report_experimental/self_report_experimental_scenarios.json'
scenarios=json.loads(source.read_text())['scenarios']
assert len(scenarios)==50
ids=[s['scenario_id'] for s in scenarios];assert len(set(ids))==50
random.Random(42).shuffle(ids)
calibration=set(ids[:10])
splits={'seed':42,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'extraction_ids':sorted(set(ids)-calibration),'calibration_ids':sorted(calibration),'held_out_evaluation':['cais/MASK','justinphan3110/machiavelli','cais/mmlu:test','openai/gsm8k:test']}
(r/'results/steering_splits.json').write_text(json.dumps(splits,indent=2)+'\n')
output=r/'results/qwen_contrast_pairs.jsonl'
done={json.loads(l)['scenario_id'] for l in output.read_text().splitlines()} if output.exists() else set()
print('Loading model; shared contrast pairs, 40 extraction / 10 calibration',flush=True)
path=r/'models/Qwen3.5-9B'
processor=AutoProcessor.from_pretrained(path,local_files_only=True)
model=AutoModelForImageTextToText.from_pretrained(path,dtype=torch.bfloat16,device_map={'':0},local_files_only=True,attn_implementation='sdpa').eval()
for s in scenarios:
 if s['scenario_id'] in done: continue
 record={'scenario_id':s['scenario_id'],'split':'calibration' if s['scenario_id'] in calibration else 'extraction','model_revision':'c202236235762e1c871ad0ccb60c8ee5ba337b9a','source':s,'max_new_tokens':256,'do_sample':False,'enable_thinking':False}
 for condition in ['honest','dishonest']:
  messages=[{'role':'system','content':s['system_prompt_'+condition]},{'role':'user','content':s['user_message']}]
  inputs=processor.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors='pt',enable_thinking=False).to('cuda:0')
  with torch.inference_mode(): out=model.generate(**inputs,max_new_tokens=256,do_sample=False)
  tokens=out[0,inputs['input_ids'].shape[1]:].tolist()
  record[condition]={'messages':messages,'completion':processor.tokenizer.decode(tokens,skip_special_tokens=True),'completion_token_ids':tokens,'input_token_ids':inputs['input_ids'][0].tolist(),'hit_token_limit':len(tokens)==256}
 with output.open('a') as f: f.write(json.dumps(record)+'\n');f.flush()
 print('PAIR COMPLETE',s['scenario_id'],record['split'],flush=True)
print('ALL 50 PAIRS COMPLETE',flush=True)
