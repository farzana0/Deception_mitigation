"""Load pinned base model and saved intervention without cluster-specific paths."""
import argparse,json,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--condition',choices=['baseline','caa','sttp','rank2','pooled','cp_scheduled','cp_static'],required=True);p.add_argument('--prompt',required=True);p.add_argument('--max-new-tokens',type=int,default=256);p.add_argument('--model-path');a=p.parse_args()
root=a.package.resolve();sys.path.insert(0,str(root/'experiments/code'))
import torch
if not torch.cuda.is_available():
 raise RuntimeError('Clean GPU reproduction requires an accessible CUDA device; no inference was run')
from transformers import AutoModelForImageTextToText,AutoProcessor
from steering import experiment as exp
revision='c202236235762e1c871ad0ccb60c8ee5ba337b9a'
kwargs={'local_files_only':True} if a.model_path else {'revision':revision}
model_id=a.model_path or 'Qwen/Qwen3.5-9B'
torch.manual_seed(42);torch.set_num_threads(8)
processor=AutoProcessor.from_pretrained(model_id,**kwargs)
model=AutoModelForImageTextToText.from_pretrained(model_id,dtype=torch.bfloat16,device_map={'':0},attn_implementation='sdpa',**kwargs).eval()
cp=a.condition.startswith('cp_')
fit=torch.load(root/'model'/('cp_fit.pt' if cp else 'fit.pt'),map_location='cpu',weights_only=False)
if cp:
 from steering.cp_exploratory import CPReplayHook
 exp.ResidualSteerer=CPReplayHook
 setting={'condition':a.condition,'strength':json.loads((root/'model/locked_cp_settings.json').read_text())['shared_strength']}
else:setting=json.loads((root/'model/locked_settings.json').read_text())['settings'][a.condition]
result,_=exp.generate(model,processor.tokenizer,model.model.language_model.layers,fit,[{'role':'user','content':a.prompt}],setting,max_new_tokens=a.max_new_tokens)
print(json.dumps(result,indent=2))
