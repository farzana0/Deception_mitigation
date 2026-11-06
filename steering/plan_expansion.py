"""Choose a fixed balanced MASK sample using completed pilot throughput."""
import collections,datetime,json,math,statistics
from steering.experiment import ROOT,RUN,write_json,digest
from steering.official_mask import complete_lines

def main():
    from datasets import load_from_disk
    folder=RUN/'judge_gptoss';summary=json.loads((folder/'paired_summary.json').read_text())
    assert summary['paired_complete_items']==12,'Save a complete paired pilot before planning expansion'
    conditions=['baseline','caa','sttp','rank2','pooled']
    items={(r['config'],r['task_id'],r['condition']):r for r in complete_lines(folder/'items.jsonl')}
    calls={r['request_id']:r for r in complete_lines(folder/'calls.jsonl')}
    costs=collections.defaultdict(list)
    for (config,task,condition),r in items.items():
        costs[config].append(sum(sum(a['seconds'] for a in calls[k]['attempts']) for k in r['request_ids']))
    # Charge each condition's full request cost, even when the pilot reused identical responses.
    judge_seconds_per_balanced_six=sum(statistics.mean(values)*5 for values in costs.values())
    generations=[r for p in RUN.glob('mask_generations*.jsonl') for r in complete_lines(p)]
    generation_seconds_per_balanced_six=max(sum(r['seconds'] for r in generations if r['condition']==c)/2 for c in conditions)
    now=datetime.datetime.now(datetime.timezone.utc)
    deadline=datetime.datetime(2026,11,6,10,30,tzinfo=datetime.timezone.utc)
    available=max(0,(deadline-now).total_seconds())
    # Reserve 40% for variance/retries and use sequential generation+judging as a conservative bound.
    rounds=max(2,math.floor(available*.60/(judge_seconds_per_balanced_six+generation_seconds_per_balanced_six)))
    datasets={config:load_from_disk(str(ROOT/'data/cais__MASK'/config/'test')) for config in sorted(costs)}
    rounds=min(rounds,min(len(ds) for ds in datasets.values()))
    selected=[]
    import hashlib
    for config,ds in datasets.items():
        for row in sorted(ds,key=lambda r:hashlib.sha256((config+str(r['task_id'])).encode()).hexdigest())[:rounds]:
            selected.append({'config':config,'task_id':str(row['task_id'])})
    plan={'selection':'Balanced first n per config by SHA256(config+task_id), includes original pilot; no outcome filtering','items':selected,'items_per_config':rounds,'created_at':now.isoformat(),'deadline':deadline.isoformat(),'budget_seconds':available,'budget_fraction':.60,'judge_seconds_per_balanced_six':judge_seconds_per_balanced_six,'generation_seconds_per_balanced_six_parallel_five_workers':generation_seconds_per_balanced_six,'costs_by_config':{k:statistics.mean(v) for k,v in costs.items()},'settings_sha256':digest(RUN/'locked_settings.json'),'pilot_summary_sha256':digest(folder/'paired_summary.json'),'pilot_items_sha256':digest(folder/'items.jsonl')}
    path=RUN/'mask_expanded_subset.json'
    if path.exists():assert json.loads(path.read_text())['items']==selected,'An expansion manifest already exists; do not change a running subset'
    else:write_json(path,plan)
    print(json.dumps({k:v for k,v in plan.items() if k!='items'},indent=2));print('selected',len(selected))
if __name__=='__main__':main()
