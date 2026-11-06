"""Retry failed auxiliary calls into an independent recovery ledger; merge only after writer exit."""
import argparse,datetime,hashlib,json,subprocess,time,urllib.request
import jsonschema
from steering.official_mask import RUN,complete_lines
from steering.grade_pilot import save
from steering.nfs_io import read_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);p.add_argument('--merge',action='store_true');p.add_argument('--writer-session',default='machiavelli-quality');a=p.parse_args()
    folder=RUN/a.folder;protocol=read_json(folder/'protocol.json');recovery=RUN/(a.folder+'_recovery');recovery.mkdir(exist_ok=True)
    calls={r['request_id']:r for r in complete_lines(folder/'calls.jsonl')};items={r['key']:r for r in complete_lines(folder/'items.jsonl')};receipts={r['request_id']:r for r in complete_lines(recovery/'calls.jsonl')}
    failed={r['request_id'] for r in items.values() if r['status']!='complete'}
    if a.merge:
        assert subprocess.run(['tmux','has-session','-t','='+a.writer_session],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0,'Canonical writer must exit before merging'
        merged=[]
        for rid in sorted(failed):
            if rid not in receipts or receipts[rid]['status']!='ok':continue
            call=receipts[rid];assert call['request']==calls[rid]['request']
            assert rid==hashlib.sha256(json.dumps({'protocol':protocol,'payload':call['request']},sort_keys=True).encode()).hexdigest()
            with (folder/'calls.jsonl').open('a') as f:f.write(json.dumps(call)+'\n');f.flush()
            for item in items.values():
                if item['request_id']!=rid or item['status']=='complete':continue
                row=item|{'status':'complete','labels':call['parsed'],'recovery_ledger':str(recovery/'calls.jsonl')}
                with (folder/'items.jsonl').open('a') as f:f.write(json.dumps(row)+'\n');f.flush()
                merged.append(row['key'])
        save(recovery/'merge.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'merged_items':merged,'same_profile':True,'canonical_writer_was_absent':True});print('MERGED',merged,flush=True);return
    for rid in sorted(failed):
        if rid in receipts and receipts[rid]['status']=='ok':print('RECOVERY SUCCESS REUSED',rid,flush=True);continue
        source=calls[rid];payload=source['request'];assert rid==hashlib.sha256(json.dumps({'protocol':protocol,'payload':payload},sort_keys=True).encode()).hexdigest()
        record={'request_id':rid,'request':payload,'protocol_sha256':hashlib.sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest(),'attempts':[],'recovery_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'same_profile_recovery':True};start=time.time()
        try:
            request=urllib.request.Request('http://127.0.0.1:8001/v1/chat/completions',json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(request,timeout=300) as f:response=json.load(f)
            record['response']=response;choice=response['choices'][0]
            if choice.get('finish_reason')=='length':raise ValueError('truncated')
            if choice['message'].get('refusal'):raise ValueError('judge_refusal')
            parsed=json.loads(choice['message'].get('content') or '');jsonschema.validate(parsed,protocol['schema']);record.update(status='ok',parsed=parsed)
        except Exception as error:record.update(status='truncated' if str(error)=='truncated' else 'technical_failure',parsed=None,error=str(error)[:500])
        record['attempts'].append({'status':record['status'],'seconds':time.time()-start})
        with (recovery/'calls.jsonl').open('a') as f:f.write(json.dumps(record)+'\n');f.flush()
        print('SAME-PROFILE RECOVERY',rid,record['status'],flush=True)
if __name__=='__main__':main()
