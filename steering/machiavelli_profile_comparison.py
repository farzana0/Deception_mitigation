"""Paired audit of auxiliary format profiles; never changes native game metrics."""
from collections import Counter
from steering.official_mask import RUN,complete_lines
from steering.grade_pilot import save
from steering.nfs_io import read_json

def compute():
    old=RUN/'machiavelli_quality_v1';new=RUN/'machiavelli_quality_v2'
    if not (old/'summary.json').exists() or not (new/'summary.json').exists():return None
    if read_json(new/'summary.json')['judged_decisions']!=2171:return None
    a={r['key']:r for r in complete_lines(old/'items.jsonl')};b={r['key']:r for r in complete_lines(new/'items.jsonl')}
    ac={r['request_id']:r for r in complete_lines(old/'calls.jsonl')};bc={r['request_id']:r for r in complete_lines(new/'calls.jsonl')}
    rows=[];dimensions=['action_decision_quality','coherence','explanation_action_consistency']
    for key in sorted(set(a)|set(b)):
        x=a.get(key);y=b.get(key);valid=x is not None and y is not None and x['status']==y['status']=='complete'
        same_inputs=None
        if x and y:
            px=ac[x['request_id']]['request'];py=bc[y['request_id']]['request'];same_inputs=px['messages'][-1]['content']==py['messages'][-1]['content'];assert same_inputs
            for field in ['model','temperature','seed','reasoning_effort','max_tokens','response_format']:assert px[field]==py[field]
        rows.append({'key':key,'v1_status':x['status'] if x else 'missing_record','v2_status':y['status'] if y else 'missing_record','same_inputs':same_inputs,'v1_request_id':x['request_id'] if x else None,'v2_request_id':y['request_id'] if y else None,'v1_labels':x['labels'] if x else None,'v2_labels':y['labels'] if y else None,'paired_valid':valid})
    paired=[r for r in rows if r['paired_valid']]
    summary={'auxiliary_only':True,'target_decisions':2171,'all_decision_pairs':len(rows),'shared_valid_decisions':len(paired),'v1_statuses':dict(Counter(r['v1_status'] for r in rows)),'v2_statuses':dict(Counter(r['v2_status'] for r in rows)),'same_state_action_response_inputs_verified':all(r['same_inputs'] for r in rows if r['same_inputs'] is not None),'model_and_decoding_identical':True,'v2_minus_v1_score_deltas':{},'v1_technical_failures':[r['key'] for r in rows if r['v1_status']!='complete'],'v2_technical_failures':[r['key'] for r in rows if r['v2_status']!='complete'],'interpretation':'Format-instruction sensitivity on identical actual decision inputs. Correlated steps are descriptive; native deception/reward metrics remain primary. Technical failures are not imputed.'}
    for dim in dimensions:
        values=[r['v2_labels'][dim]-r['v1_labels'][dim] for r in paired if r['v1_labels'][dim] is not None and r['v2_labels'][dim] is not None]
        summary['v2_minus_v1_score_deltas'][dim]={'n':len(values),'mean':sum(values)/len(values) if values else None}
    summary['random_behavior_label_disagreements']=sum(r['v1_labels']['ungrounded_or_random_behavior']!=r['v2_labels']['ungrounded_or_random_behavior'] for r in paired)
    save(RUN/'machiavelli_auxiliary_profile_comparison_items.json',rows);save(RUN/'machiavelli_auxiliary_profile_comparison.json',summary);return summary
if __name__=='__main__':print(compute())
