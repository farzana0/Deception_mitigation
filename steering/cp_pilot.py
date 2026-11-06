"""Two-condition predeclared CP pilot; no writes to main-run artifacts."""
import argparse,datetime,hashlib,json,os,time
from pathlib import Path
import torch
from steering import experiment as exp
from steering.cp_exploratory import CPReplayHook,OUT,ROOT,RUN,digest
from steering.grade_pilot import save
from steering.official_mask import complete_lines
from steering.journal import repair_tail
CONDITIONS=['cp_scheduled','cp_static']
DEADLINE=datetime.datetime(2026,11,6,21,15,tzinfo=datetime.timezone.utc).timestamp()

def risky():
    if (OUT/'yield_gpu6.request').exists():return True
    p=ROOT/'MAIN_THROUGHPUT_STATUS.json'
    return p.exists() and json.loads(p.read_text()).get('cp_budget_signal',{}).get('buffered_main_deadline_at_risk',True)

def main():
    assert (OUT/'initial_gate.json').exists() and json.loads((OUT/'initial_gate.json').read_text())['status']=='passed'
    protocol=json.loads((OUT/'predeclared_protocol.json').read_text());lock=json.loads((OUT/'locked_cp_settings.json').read_text());alpha=lock['shared_strength']
    assert digest(RUN/'locked_settings.json')==protocol['original_settings_sha256']
    model,tokenizer,layers=exp.load();fit=torch.load(OUT/'cp_fit.pt',weights_only=False)
    exp.ResidualSteerer=CPReplayHook
    pair=next(p for p in exp.read_pairs() if p['split']=='calibration');s=pair['source']
    messages=[{'role':'system','content':s['system_prompt_neutral']},{'role':'user','content':s['user_message']}]
    timings=[]
    for condition in CONDITIONS:
        start=time.time();result,_=exp.generate(model,tokenizer,layers,fit,messages,{'condition':condition,'strength':alpha},max_new_tokens=256)
        elapsed=time.time()-start;stats=result['stats']
        assert abs(stats['realized_relative_rms_total_per_step']-alpha)<.005
        timings.append({'condition':condition,'seconds':elapsed,'generated_tokens':len(result['token_ids']),'stats':stats,'calibration_scenario_id':pair['scenario_id']})
    save(OUT/'realized_norm_and_timing_smoke.json',{'status':'passed','shared_strength':alpha,'timings':timings,'not_held_out_data':True,'completed_epoch':time.time()})
    # Conservative cap-based estimate, including 4 sec prefill overhead per prompt.
    per_prompt=max(t['seconds']/max(1,t['generated_tokens']-1)*256+4 for t in timings)
    serial_generation_bound=24*4*2*per_prompt
    # At most 4 judge calls per item per condition, each budgeted at 15 sec, plus 10min buffer.
    serial_judge_bound=24*4*2*15+600
    pilot_bound=3*serial_generation_bound+serial_judge_bound
    print('CP TIMING SMOKE',json.dumps(timings),'conservative seconds',pilot_bound,flush=True)
    while True:
        now=time.time();p=ROOT/'MAIN_THROUGHPUT_STATUS.json'
        main_budget=json.loads(p.read_text()) if p.exists() else {}
        budget=main_budget.get('cp_budget_signal',{})
        ready=not budget.get('defer_pilot_until_main_acceleration_benchmarked',True)
        if risky() or now+pilot_bound>=DEADLINE:
            save(OUT/'pilot_gate.json',{'decision':'do_not_launch','reason':'Main deadline at risk or both CP conditions cannot fit by21:15UTC','fit_and_smoke_saved':True,'main_budget':main_budget,'pilot_bound_seconds':pilot_bound});return
        if ready:
            # Include availability of the original five-condition comparison context.
            eta=main_budget.get('eta',{}).get('stratified_with_30pct_buffer_ready_utc')
            main_finish=datetime.datetime.fromisoformat(eta).timestamp() if eta else DEADLINE
            if max(now+pilot_bound,main_finish+serial_judge_bound)<DEADLINE:
                save(OUT/'pilot_gate.json',{'decision':'launch_both','main_capacity_reserved':True,'main_budget':main_budget,'pilot_bound_seconds':pilot_bound,'predicted_own_completion_epoch':now+pilot_bound,'context_completion_bound_epoch':main_finish+serial_judge_bound,'shared_strength':alpha,'protocol_sha256':digest(OUT/'predeclared_protocol.json'),'decision_epoch':now});break
        print('CP WAITING FOR BENCHMARKED MAIN CAPACITY',flush=True);time.sleep(30)
    from datasets import load_from_disk
    selected=json.loads((OUT/'pilot_manifest.json').read_text())['items'];datasets={c:load_from_disk(str(ROOT/'data/cais__MASK'/c/'test')) for c in {i['config'] for i in selected}}
    path=OUT/'pilot_generations.jsonl';repair_tail(path)
    done={(r['config'],r['task_id'],r['condition'],r['prompt_type']) for r in complete_lines(path)}
    for item in selected:
        config,task=item['config'],item['task_id'];row=next(r for r in datasets[config] if str(r['task_id'])==task)
        messages=[{'role':'system','content':row['system_prompt']}]
        if config=='doubling_down_known_facts':messages.extend([{'role':'user','content':row['dd_turn_1_prompt']},{'role':'assistant','content':row['dd_turn_1_response']}])
        messages.append({'role':'user','content':row['user_prompt']});prompts={'pressured':messages}
        for k in [1,2,3]:
            if row.get('belief_elicit_'+str(k)):prompts['belief_'+str(k)]=[{'role':'system','content':'You are a helpful assistant.'},{'role':'user','content':row['belief_elicit_'+str(k)]}]
        for prompt_type,prompt in prompts.items():
            # Alternate modes to give both equal progress and never prioritize a single variant.
            for condition in CONDITIONS:
                key=(config,task,condition,prompt_type)
                if key in done:continue
                if time.time()>=DEADLINE or risky():
                    save(OUT/'pilot_interrupted.json',{'reason':'CPdeadline or mainpriority safeguard','epoch':time.time(),'completed_prompts':len(done)});return
                start=time.time();result,_=exp.generate(model,tokenizer,layers,fit,prompt,{'condition':condition,'strength':alpha},max_new_tokens=256);result.pop('trace')
                record={'config':config,'task_id':task,'condition':condition,'prompt_type':prompt_type,'messages':prompt,'result':result,'seconds':time.time()-start,'settings_sha256':protocol['original_settings_sha256'],'cp_settings_sha256':digest(OUT/'locked_cp_settings.json'),'protocol_sha256':digest(OUT/'predeclared_protocol.json')}
                with path.open('a') as f:f.write(json.dumps(record)+'\n');f.flush()
                done.add(key);print('CP PILOT GENERATED',*key,len(done),flush=True)
    save(OUT/'generation_complete.json',{'complete':True,'epoch':time.time(),'prompts':len(done),'items_per_condition':24,'conditions':CONDITIONS})

if __name__=='__main__':main()
