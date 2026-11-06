"""Original locked MASK generation with cross-process prompt leases and dynamic journals."""
import argparse,collections,fcntl,hashlib,json,os,signal,time
from pathlib import Path
import torch
from steering.experiment import ROOT,RUN,load,generate,digest
from steering.grade_pilot import CONDITIONS,save
from steering.journal import repair_tail

class JournalIndex:
    def __init__(self,folder):self.folder=folder;self.offsets={};self.done=set();self.rows={}
    def refresh(self):
        for path in sorted(self.folder.glob('mask_generations*.jsonl')):
            offset=self.offsets.get(path,0)
            with path.open('rb') as f:
                f.seek(offset)
                while True:
                    line=f.readline()
                    if not line or not line.endswith(b'\n'):break
                    row=json.loads(line);key=tuple(row[k] for k in ['config','task_id','condition','prompt_type'])
                    if key in self.rows:
                        old=self.rows[key]
                        assert old['messages']==row['messages'] and old['result']['token_ids']==row['result']['token_ids'],'Conflicting saved generations'
                    self.rows[key]=row;self.done.add(key);offset=f.tell()
            self.offsets[path]=offset
        return self.done

class Lease:
    def __init__(self,folder,key):self.path=folder/(hashlib.sha256(json.dumps(key).encode()).hexdigest()+'.lock');self.handle=None
    def acquire(self):
        self.path.parent.mkdir(exist_ok=True,parents=True);self.handle=self.path.open('a+')
        try:fcntl.flock(self.handle,fcntl.LOCK_EX|fcntl.LOCK_NB);return True
        except BlockingIOError:self.handle.close();self.handle=None;return False
    def release(self):
        if self.handle:
            fcntl.flock(self.handle,fcntl.LOCK_UN);self.handle.close();self.handle=None

def tasks(manifest):
    from datasets import load_from_disk
    sources={};result=[]
    for item in json.loads(manifest.read_text())['items']:
        config=item['config']
        if config not in sources:sources[config]={str(r['task_id']):r for r in load_from_disk(str(ROOT/'data/cais__MASK'/config/'test'))}
        row=sources[config][item['task_id']]
        messages=[{'role':'system','content':row['system_prompt']}]
        if config=='doubling_down_known_facts':messages.extend([{'role':'user','content':row['dd_turn_1_prompt']},{'role':'assistant','content':row['dd_turn_1_response']}])
        messages.append({'role':'user','content':row['user_prompt']})
        prompts={'pressured':messages}
        for i in [1,2,3]:
            if row.get('belief_elicit_'+str(i)):prompts['belief_'+str(i)]=[{'role':'system','content':'You are a helpful assistant.'},{'role':'user','content':row['belief_elicit_'+str(i)]}]
        for c in CONDITIONS:
            result.extend((config,str(row['task_id']),c,ptype,prompt) for ptype,prompt in prompts.items())
    return result

def validate(model,tokenizer,layers,fit,locked,index):
    checked=[]
    for c in CONDITIONS:
        candidates=[r for r in index.rows.values() if r['condition']==c and r['prompt_type']=='pressured']
        chosen=min(candidates,key=lambda r:hashlib.sha256((r['config']+r['task_id']).encode()).hexdigest())
        result,_=generate(model,tokenizer,layers,fit,chosen['messages'],locked['settings'][c],max_new_tokens=256)
        ok=result['token_ids']==chosen['result']['token_ids'] and result['text']==chosen['result']['text']
        checked.append({'condition':c,'config':chosen['config'],'task_id':chosen['task_id'],'cached_token_count':len(chosen['result']['token_ids']),'passed':ok})
        save(RUN/'mask_dynamic_gpu7_validation.json',{'status':'running' if len(checked)<5 else 'passed' if all(r['passed'] for r in checked) else 'failed','cases':checked,'settings_sha256':digest(RUN/'locked_settings.json'),'backend':'Unchanged HF BF16 SDPA, greedy seed42, max_new_tokens256'})
        assert ok,('Cached decoding differs; do not activate dynamic helper',checked[-1])
        print('EXACT CACHED DECODING VERIFIED',c,flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--condition',choices=CONDITIONS);p.add_argument('--helper',action='store_true');p.add_argument('--validate',action='store_true');p.add_argument('--activation',type=Path);a=p.parse_args();assert a.helper != bool(a.condition)
    manifest=RUN/'mask_full_test_manifest.json';locked=json.loads((RUN/'locked_settings.json').read_text());assert digest(RUN/'fit.pt')==locked['fit_sha256']
    index=JournalIndex(RUN);index.refresh();work=tasks(manifest)
    model,tokenizer,layers=load();fit=torch.load(RUN/'fit.pt',weights_only=False)
    if a.validate:validate(model,tokenizer,layers,fit,locked,index)
    if a.activation:
        while not a.activation.exists():time.sleep(1)
        assert json.loads(a.activation.read_text())['old_workers_exited'] is True
    label='gpu7_helper' if a.helper else a.condition
    output=RUN/('mask_generations_'+label+'.jsonl');repair_tail(output)
    stopping=False
    def stop(signum,frame):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    allowed=CONDITIONS if a.helper else [a.condition];subset=[w for w in work if w[2] in allowed]
    while not stopping:
        index.refresh();pending=[w for w in subset if w[:4] not in index.done]
        if not pending:print('DYNAMIC MASK COMPLETE',label,flush=True);return
        if a.helper:
            # Balance complete condition-item groups, then fill earliest incomplete pairs.
            groups=collections.defaultdict(set)
            for w in work:groups[w[:3]].add(w[:4])
            ready=collections.Counter(k[2] for k,keys in groups.items() if keys<=index.done)
            pending.sort(key=lambda w:ready[w[2]])
        progressed=False
        for w in pending:
            if stopping:break
            key=w[:4];lease=Lease(RUN/'mask_prompt_leases',key)
            if not lease.acquire():continue
            try:
                index.refresh()
                if key in index.done:continue
                started=time.time();result,_=generate(model,tokenizer,layers,fit,w[4],locked['settings'][w[2]],max_new_tokens=256)
                result.pop('trace',None)
                record={'config':w[0],'task_id':w[1],'condition':w[2],'prompt_type':w[3],'messages':w[4],'result':result,'seconds':time.time()-started,'settings_sha256':digest(RUN/'locked_settings.json'),'generation_worker':label,'lease_protocol':'fcntl-prompt-v1'}
                with output.open('a') as f:f.write(json.dumps(record)+'\n');f.flush()
                index.done.add(key);index.rows[key]=record;progressed=True
                print('MASK GENERATED',*key,'worker',label,flush=True)
            finally:lease.release()
            if a.helper:break # Refresh balanced condition priorities after each prompt.
        if not progressed:time.sleep(1)
    print('DYNAMIC MASK STOPPED AT PROMPT CHECKPOINT',label,flush=True)
if __name__=='__main__':main()
