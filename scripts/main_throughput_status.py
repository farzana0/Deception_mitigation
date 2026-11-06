"""One-shot main MASK throughput and resource signal, with persistent observed samples."""
import collections,csv,datetime,json,statistics,subprocess
from pathlib import Path
from steering.mask_dynamic import JournalIndex,tasks
from steering.official_mask import ROOT,RUN
from steering.grade_pilot import CONDITIONS,save

def main():
    now=datetime.datetime.now(datetime.timezone.utc);deadline=datetime.datetime(2026,11,6,22,tzinfo=datetime.timezone.utc)
    index=JournalIndex(RUN);index.refresh();work=tasks(RUN/'mask_full_test_manifest.json');expected={w[:4] for w in work};groups=collections.defaultdict(set)
    for w in work:groups[w[:3]].add(w[:4])
    ready={c:{k[:2] for k,keys in groups.items() if k[2]==c and keys<=index.done} for c in CONDITIONS}
    common=set.intersection(*ready.values());primary=json.loads((RUN/'judge_gptoss_full/paired_summary.json').read_text());judged=primary['paired_complete_items']
    history=RUN/'main_throughput_samples.jsonl';old=[json.loads(l) for l in history.read_text().splitlines()] if history.exists() else []
    current={'utc':now.isoformat(),'ready_paired':len(common),'judged_paired':judged,'saved_prompts':len(expected&index.done),'ready_by_condition':{c:len(ready[c]) for c in CONDITIONS},'judge_calls_ok':primary.get('judge_call_statuses',{}).get('ok',0)}
    with history.open('a') as f:f.write(json.dumps(current)+'\n')
    start=datetime.datetime(2026,11,6,9,20,41,tzinfo=datetime.timezone.utc);elapsed=(now-start).total_seconds()/3600
    rates={'ready_since_full_start_per_hour':(len(common)-240)/elapsed,'judged_since_full_start_per_hour':(judged-240)/elapsed}
    recent=[r for r in old if (now-datetime.datetime.fromisoformat(r['utc'])).total_seconds()>=600]
    if recent:
        past=recent[-1];hours=(now-datetime.datetime.fromisoformat(past['utc'])).total_seconds()/3600
        rates|={'recent_ready_per_hour':(len(common)-past['ready_paired'])/hours,'recent_judged_per_hour':(judged-past['judged_paired'])/hours,'recent_window_hours':hours,'recent_prompt_per_hour':(current['saved_prompts']-past['saved_prompts'])/hours}
    # Per-condition/config/prompt-type historical timings include the complete fixed 240 cohort.
    timings=collections.defaultdict(list)
    for k,r in index.rows.items():timings[k[2],k[0],k[3]].append(r['seconds'])
    fallback=statistics.mean(r['seconds'] for r in index.rows.values());remaining={c:0. for c in CONDITIONS};pending_counts=collections.Counter()
    for w in work:
        if w[:4] in index.done:continue
        cell=timings[w[2],w[0],w[3]];seconds=statistics.mean(cell[-40:]) if cell else fallback
        remaining[w[2]]+=seconds;pending_counts[w[2]]+=1
    low=0.;high=max(remaining.values())
    for _ in range(60):
        middle=(low+high)/2
        if sum(max(0,x-middle) for x in remaining.values())>middle:low=middle
        else:high=middle
    validation_path=RUN/'mask_dynamic_gpu7_validation.json';validation=json.loads(validation_path.read_text()) if validation_path.exists() else {'status':'not_started'}
    activation=RUN/'mask_dynamic_activation.json';active=activation.exists()
    model_seconds=high if active else max(remaining.values());eta_model=now+datetime.timedelta(seconds=model_seconds)
    eta_conservative=now+datetime.timedelta(seconds=model_seconds*1.3)
    rate=rates.get('recent_ready_per_hour',rates['ready_since_full_start_per_hour']);eta_linear=now+datetime.timedelta(hours=(1000-len(common))/rate) if rate>0 else None
    gpu_output=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True)
    roles=['main baseline','main CAA','main StTP','main rank2','main pooled','healthy existing unsteered judge','root-owned CP preparation / reserved by root','main helper' if active else 'reserved main acceleration validation']
    gpu=[]
    for row in csv.reader(gpu_output.splitlines()):
        i=int(row[0]);gpu.append({'gpu':i,'used_mib':int(row[1]),'utilization_pct':int(row[2]),'role':roles[i]})
    activation_data=json.loads(activation.read_text()) if active else None
    post_activation_seconds=(now-datetime.datetime.fromisoformat(activation_data['utc'])).total_seconds() if active else 0
    benchmark_path=RUN/'mask_dynamic_benchmark.json'
    benchmark=json.loads(benchmark_path.read_text()) if benchmark_path.exists() else None
    if active and post_activation_seconds>=600 and benchmark is None:
        post=[r for r in old if datetime.datetime.fromisoformat(r['utc'])>=datetime.datetime.fromisoformat(activation_data['utc'])]
        if post:
            anchor=post[0];hours=(now-datetime.datetime.fromisoformat(anchor['utc'])).total_seconds()/3600
            if hours>=1/6:
                pre=[r for r in old if datetime.datetime.fromisoformat(r['utc'])<datetime.datetime.fromisoformat(activation_data['utc'])]
                baseline=pre[-1] if pre else None
                benchmark={'utc':now.isoformat(),'window_start_utc':anchor['utc'],'window_hours':hours,'ready_pairs_added':len(common)-anchor['ready_paired'],'judged_pairs_added':judged-anchor['judged_paired'],'saved_prompts_added':current['saved_prompts']-anchor['saved_prompts'],'ready_pairs_per_hour':(len(common)-anchor['ready_paired'])/hours,'judged_pairs_per_hour':(judged-anchor['judged_paired'])/hours,'saved_prompts_per_hour':(current['saved_prompts']-anchor['saved_prompts'])/hours,'pre_handoff_observation':baseline,'interpretation':'Short observational throughput window includes balancing catch-up and warmup; future strata and judge contention may differ. Same locked settings/decoding.'}
                save(benchmark_path,benchmark)
    safety=(deadline-eta_conservative).total_seconds()/3600
    result={'utc':now.isoformat(),'deadline_utc':deadline.isoformat(),'target_items':1000,'ready':current,'judged':judged,'rates':rates,'bottleneck':'generation' if len(common)-judged<10 else 'judge catchup','eta':{'linear_ready_utc':eta_linear.isoformat() if eta_linear else None,'stratified_remaining_work_ready_utc':eta_model.isoformat(),'stratified_with_30pct_buffer_ready_utc':eta_conservative.isoformat(),'buffered_slack_hours_before_22UTC':safety,'remaining_serial_generation_seconds_by_condition':remaining,'remaining_prompt_counts_by_condition':dict(pending_counts),'limitations':'Timing estimates use saved historical condition/stratum/prompt-type means; future token lengths, contention and model reload overhead can change them. Paired throughput must be benchmarked after activation. Judge backlog currently tracked separately.'},'actual_gpu_allocations':gpu,'acceleration_benchmark':benchmark,'gpu7_validation':validation,'dynamic_activation':json.loads(activation.read_text()) if active else None,'safe_acceleration_plan':'GPU7 exact cached-decoding verification first; then stop old static-done clients, verify exit and preserved journals; replace generation clients with prompt-lease-aware per-condition writers plus one balanced GPU7 helper. Same model/fit/settings/decoding; readers already combine worker journals. No CP path edits and no judge server restart.','cp_budget_signal':{'defer_pilot_until_main_acceleration_benchmarked':not active or post_activation_seconds<600 or 'recent_ready_per_hour' not in rates,'buffered_main_deadline_at_risk':safety<.5,'root_owns_CP_gate':True},'freeze_policy':json.loads((ROOT/'Deception_mitigation/configs/report_freeze.json').read_text())}
    for path in [ROOT/'MAIN_THROUGHPUT_STATUS.json',ROOT/'Deception_mitigation/MAIN_THROUGHPUT_STATUS.json',RUN/'MAIN_THROUGHPUT_STATUS.json']:save(path,result)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
