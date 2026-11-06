"""Offline verification of blinded auxiliary labels and their saved-response bindings."""
import collections,datetime,hashlib,json
from pathlib import Path
from steering.official_mask import RUN,complete_lines
from steering.grade_pilot import CONDITIONS,save
from steering.response_status import FOLDER,FIELDS,SCHEMA,DEFINITION

def main():
    protocol=json.loads((FOLDER/'protocol.json').read_text());assert protocol['definition']==DEFINITION and protocol['schema']==SCHEMA
    assert json.loads((FOLDER/'validation.json').read_text())['status']=='passed'
    calls={r['request_id']:r for r in complete_lines(FOLDER/'calls.jsonl')}
    for request_id,r in calls.items():
        p=r['request'];assert r['status']=='ok' and r['judgment_type']=='response_status_v1'
        assert p['model']=='openai/gpt-oss-20b' and p['temperature']==0 and p['seed']==42 and p['max_tokens']==2048 and p['reasoning_effort']=='low'
        assert p['messages'][0]=={'role':'developer','content':DEFINITION} and 'condition' not in p
        assert p['response_format']['json_schema']['schema']==SCHEMA
        expected=hashlib.sha256(json.dumps({'payload':p,'judge_revision':r['judge_revision'],'judgment_type':'response_status_v1'},sort_keys=True).encode()).hexdigest();assert expected==request_id
        assert r['judge_revision']==protocol['judge']
        choice=r['response']['choices'][0];assert choice['finish_reason']!='length' and not choice['message'].get('refusal')
        parsed=json.loads(choice['message']['content']);assert set(parsed)==set(FIELDS) and all(type(v) is bool for v in parsed.values()) and parsed==r['parsed']
    selected={(i['config'],i['task_id']) for i in json.loads((RUN/'mask_expanded_subset.json').read_text())['items']}
    expected={(config,task,c) for config,task in selected for c in CONDITIONS}
    generations={(r['config'],r['task_id'],r['condition']):r for p in RUN.glob('mask_generations*.jsonl') for r in complete_lines(p) if r['prompt_type']=='pressured' and (r['config'],r['task_id']) in selected}
    items={(r['config'],r['task_id'],r['condition']):r for r in complete_lines(FOLDER/'items.jsonl')}
    assert set(items)==set(generations)==expected and len(items)==1200
    for key,item in items.items():
        assert item['status']=='complete' and item['judgment_type']=='response_status_v1'
        call=calls[item['request_id']];generation=generations[key]
        quoted=json.loads(call['request']['messages'][1]['content'])
        assert quoted=={'actor_conversation':generation['messages'],'actor_response':generation['result']['text']}
        assert item['labels']==call['parsed'] and item['settings_sha256']==generation['settings_sha256']
    summary=json.loads((FOLDER/'paired_summary.json').read_text());assert summary['paired_complete_items']==summary['target_items']==240
    for c in CONDITIONS:
        values=[r for key,r in items.items() if key[2]==c];s=summary['conditions'][c]
        assert s['complete_items']==s['paired_denominator']==len(values)==240 and s['technical_item_failures']==0
        for field,label in [('explicit_refusal_count','explicit_refusal'),('epistemic_abstention_count','epistemic_abstention')]:assert s[field]==sum(r['labels'][label] for r in values)
        assert s['overlap_count']==sum(all(r['labels'].values()) for r in values)
    result={'status':'passed','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'paired_items':240,'condition_item_labels_verified':1200,'unique_judge_calls_verified':len(calls),'payload_hashes_and_response_bindings_verified':True,'condition_metadata_absent_from_requests':True,'primary_core_calls_sha256':hashlib.sha256((RUN/'judge_gptoss_expanded/calls.jsonl').read_bytes()).hexdigest(),'auxiliary_calls_sha256':hashlib.sha256((FOLDER/'calls.jsonl').read_bytes()).hexdigest(),'conditions':summary['conditions']}
    save(FOLDER/'audit.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
