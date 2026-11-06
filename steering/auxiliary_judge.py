"""Versioned, local-only auxiliary structured judging; never changes MASK transport."""
import concurrent.futures,hashlib,json,threading,time,urllib.request
import jsonschema
from steering.official_mask import RUN,complete_lines
from steering.grade_pilot import save
from steering.journal import repair_tail

class Judge:
    def __init__(self,name,definition,schema,cap=4096):
        self.folder=RUN/name;self.folder.mkdir(exist_ok=True)
        self.path=self.folder/'calls.jsonl';repair_tail(self.path)
        self.cache={r['request_id']:r for r in complete_lines(self.path)}
        self.lock=threading.Lock();self.inflight={}
        self.protocol={'name':name,'definition':definition,'schema':schema,'max_tokens':cap,'temperature':0,'seed':42,'reasoning_effort':'low','judge':json.loads((RUN/'judge_model.json').read_text()),'auxiliary_only':True}
        path=self.folder/'protocol.json'
        if path.exists():assert json.loads(path.read_text())==self.protocol,'Changed profile requires new folder'
        else:save(path,self.protocol)
    def call(self,data):
        p=self.protocol
        payload={'model':'openai/gpt-oss-20b','messages':[{'role':'developer','content':p['definition']},{'role':'user','content':json.dumps(data,ensure_ascii=False)}],'temperature':0,'seed':42,'reasoning_effort':'low','max_tokens':p['max_tokens'],'response_format':{'type':'json_schema','json_schema':{'name':'AuxiliaryEvaluation','strict':True,'schema':p['schema']}}}
        rid=hashlib.sha256(json.dumps({'protocol':p,'payload':payload},sort_keys=True).encode()).hexdigest()
        while True:
            with self.lock:
                if rid in self.cache and self.cache[rid]['status']=='ok':return self.cache[rid]
                if rid not in self.inflight:
                    self.inflight[rid]=threading.Event();break
                event=self.inflight[rid]
            event.wait()
        record={'request_id':rid,'request':payload,'protocol_sha256':hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest(),'attempts':[]}
        try:
            for attempt in range(3):
                start=time.time()
                try:
                    req=urllib.request.Request('http://127.0.0.1:8001/v1/chat/completions',json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
                    with urllib.request.urlopen(req,timeout=300) as f:response=json.load(f)
                    record['response']=response;choice=response['choices'][0]
                    if choice.get('finish_reason')=='length':raise ValueError('truncated')
                    if choice['message'].get('refusal'):raise ValueError('judge_refusal')
                    parsed=json.loads(choice['message'].get('content') or '')
                    jsonschema.validate(parsed,p['schema'])
                    record.update(status='ok',parsed=parsed);record['attempts'].append({'status':'ok','seconds':time.time()-start,'response':response});break
                except Exception as e:
                    status=str(e) if str(e) in ['truncated','judge_refusal'] else 'technical_failure'
                    record.update(status=status,parsed=None);record['attempts'].append({'status':status,'error':str(e)[:500],'seconds':time.time()-start,'response':record.get('response')});time.sleep(1)
            with self.lock:
                with self.path.open('a') as f:f.write(json.dumps(record)+'\n');f.flush()
                self.cache[rid]=record
            return record
        finally:
            with self.lock:self.inflight.pop(rid).set()

def obj(properties):return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
def string():return {'type':'string'}
def boolean():return {'type':'boolean'}
def score(nullable=False):return {'type':['integer','null'] if nullable else 'integer','minimum':0,'maximum':4}

def process(judge,work,workers=1):
    """One writer per item journal; successful calls and item bindings are resumed."""
    path=judge.folder/'items.jsonl';repair_tail(path)
    items={r['key']:r for r in complete_lines(path)}
    pending=[w for w in work if w['key'] not in items or items[w['key']]['status']!='complete']
    def run(w):
        call=judge.call(w['data'])
        return {k:v for k,v in w.items() if k!='data'}|{'request_id':call['request_id'],'status':'complete' if call['status']=='ok' else 'technical_failure','labels':call['parsed']}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(run,w):w for w in pending}
        for future in concurrent.futures.as_completed(futures):
            row=future.result()
            with path.open('a') as f:f.write(json.dumps(row)+'\n');f.flush()
            items[row['key']]=row
            print(judge.folder.name,row['key'],row['status'],'complete',sum(r['status']=='complete' for r in items.values()),flush=True)
    return items
