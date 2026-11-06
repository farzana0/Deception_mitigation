"""Paired capability pilots after the core MASK comparison is complete."""
import argparse,json,hashlib,re
import torch
from steering.journal import repair_tail
from steering.official_mask import complete_lines
from steering.experiment import ROOT,RUN,load,generate,write_json,digest

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--condition',required=True);args=parser.parse_args()
    assert (RUN/'locked_settings.json').exists()
    from datasets import load_from_disk
    locked=json.loads((RUN/'locked_settings.json').read_text());fit=torch.load(RUN/'fit.pt',weights_only=False)
    model,tokenizer,layers=load()
    output=RUN/('capability_'+args.condition+'.jsonl')
    repair_tail(output)
    existing=complete_lines(output)
    done={(r['benchmark'],r['index']) for r in existing}
    for benchmark,relative,count in [('mmlu','cais__mmlu/all/test',30),('gsm8k','openai__gsm8k/main/test',10)]:
        ds=load_from_disk(str(ROOT/'data'/relative))
        indices=sorted(range(len(ds)),key=lambda i:hashlib.sha256((benchmark+str(i)).encode()).hexdigest())[:count]
        for index in indices:
            if (benchmark,index) in done:continue
            row=ds[index]
            if benchmark=='mmlu':
                question=row['question']+'\n'+'\n'.join(f'{chr(65+i)}. {choice}' for i,choice in enumerate(row['choices']))+'\nRespond with only the correct letter: A, B, C, or D.'
                expected=chr(65+row['answer']);limit=32
            else:
                question=row['question']+'\nSolve the problem. End with a line: #### <numeric answer>.'
                expected=row['answer'].split('####')[-1].strip().replace(',','');limit=512
            result,_=generate(model,tokenizer,layers,fit,[{'role':'user','content':question}],locked['settings'][args.condition],max_new_tokens=limit)
            text=result['text']
            if benchmark=='mmlu':
                match=re.search(r'\b([ABCD])\b',text);prediction=match.group(1) if match else None
            else:
                match=re.search(r'####\s*([-+]?\d[\d,]*(?:\.\d+)?)',text);prediction=match.group(1).replace(',','') if match else None
            correct=prediction==expected
            if benchmark=='gsm8k' and prediction is not None:
                try:correct=float(prediction)==float(expected)
                except ValueError:pass
            record={'condition':args.condition,'benchmark':benchmark,'index':index,'expected':expected,'prediction':prediction,'correct':correct,'result':result,'settings_sha256':digest(RUN/'locked_settings.json')}
            with output.open('a') as f:f.write(json.dumps(record)+'\n')
            print('CAPABILITY',args.condition,benchmark,index,correct,flush=True)
    print('CAPABILITY COMPLETE',args.condition,flush=True)

if __name__=='__main__':main()
