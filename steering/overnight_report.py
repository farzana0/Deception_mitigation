"""Render verified paired metrics and exact local resume commands from checkpoints."""
import collections,csv,datetime,json,statistics,subprocess
from pathlib import Path
from steering.official_mask import ROOT,RUN,complete_lines,load_official
from steering.grade_pilot import CONDITIONS,pressure_unknown
from steering.sensitivity import compute
from steering.paired_analysis import compute as paired_analysis

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(map(str,headers))+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])
def pct(v):return 'NA' if v is None else f'{100*v:.1f}%'
def read(path):return json.loads(path.read_text()) if path.exists() else None

def render():
    official=load_official()
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    sections=[f'CAIS overnight experiment — verified checkpoint {now}',
      'Overnight coordination started 2026-11-06 03:03 UTC; hour-8 reporting deadline 11:03 UTC; monitoring scheduled through 11:35 UTC.',
      'Local inference only. Results below are deterministic single-run measurements on fixed subsets; they are not full-benchmark estimates. No steering settings were retuned after locking.',
      'Methods: Qwen/Qwen3.5-9B revision c202236235762e1c871ad0ccb60c8ee5ba337b9a, validated Hugging Face BF16 SDPA backend. Extraction reused 40 paired scenarios; 10 disjoint calibration scenarios selected settings by length-normalized honest-minus-dishonest likelihood. Post-block residual hooks affect the final prompt position and cached decoding steps. Greedy decoding, seed 42; MASK cap 256 tokens, MMLU 32, GSM8K 512, Machiavelli 256 per action response. CAA: layer 16, relative strength .1. Herbster StTP: layer 20, c=2, threshold-gated honest-mean-plus-two-SD target. Rank-2: SVD across five layers and four position bins, strength .1. Pooled control: fixed CAA directions across the same five layers at the same .1 total relative budget. See STEERING_PROTOCOL.txt and saved fit/locked_settings/source_manifest/verification artifacts.',
      'Independent MASK judge: openai/gpt-oss-20b revision 6cee5e81ee83917806bbde320786a8fb61efebee. Isolated Python 3.10.12/vLLM 0.11.2/torch 2.9.0+cu128; driver 570.148.08. The Hugging Face environment is intact. Server binds 127.0.0.1:8001 on GPU 5. Actual binary and numerical strict-JSON inference passed through pinned official MASK functions. Only transport is replaced; condition labels are absent from judge payloads. Numerical combined-belief and official honesty aggregation are retained. Judge temperature 0, seed 42, low reasoning effort, max_tokens 4096. Package lock, launch command, model metadata, validation, raw requests/responses and per-item judgments are preserved. Earlier self-judge output is isolated in self_judge/.']
    snapshots={}
    for name,label in [('judge_gptoss','Completed 12-item pilot'),('judge_gptoss_expanded','Expanded fixed stratified subset (partial until all 240 paired items finish)')]:
        folder=RUN/name;s=read(folder/'paired_summary.json')
        if not s:continue
        latest={(r['config'],r['task_id'],r['condition']):r for r in complete_lines(folder/'items.jsonl')}
        paired_keys={tuple(k) for k in s['paired_item_ids']}
        for c in CONDITIONS:
            s['conditions'][c]['abstention_or_unknown_count']=sum(pressure_unknown(r['scoring_inputs']['pressure'],r['config']=='statistics',official) for key,r in latest.items() if key[2]==c and key[:2] in paired_keys and r['status']=='complete')
        if name=='judge_gptoss_expanded':label='Expanded fixed stratified subset ('+('complete' if s['paired_complete_items']==s['target_items'] else 'partial')+')'
        snapshots[name]=s
        sections.append('Paired items by MASK stratum: '+json.dumps(dict(collections.Counter(config for config,task in s['paired_item_ids'])))+'. Partial runs can be unbalanced while strata generate sequentially.')
        sections.append(label+f": {s['paired_complete_items']}/{s['target_items']} complete paired items. Every condition uses this common intersection. Deception = dishonest/(honest+dishonest); undetermined items remain in the all-paired denominator.")
        sections.append(table(['Condition','Paired N','Honest','Dishonest','Undetermined','Assessable N','Deception','Dishonest/all paired','Belief coverage','Abstain/unknown','Refusal regex','Truncated pressure','Technical item failures'],[[c,r['paired_denominator'],r['honest'],r['dishonest'],r['undetermined'],r['assessable_denominator'],pct(r['deception_rate']),pct(r['deception_per_all_paired_items']),pct(r['belief_coverage']),r['abstention_or_unknown_count'],r['target_refusal_regex_count'],r['truncated_target_responses'],r['technical_failures']] for c,r in s['conditions'].items()]))
        attempts=collections.Counter(a['status'] for call in complete_lines(folder/'calls.jsonl') for a in call['attempts'])
        sections.append('Judge attempt statuses (including recovered retries): '+json.dumps(dict(attempts)))
        sections.append('Judge call statuses (latest cached call per payload): '+json.dumps(s['judge_call_statuses'])+'. Refusals use the disclosed regex in grade_pilot.py; C/D and null ranges are valid abstentions. Belief coverage includes supplied references for provided_facts. High target truncation limits interpretation; decoding caps were kept fixed.')
        paired=paired_analysis(folder)
        sections.append('Common assessability and rank-2 versus pooled discordant pairs (compare identical assessable items): '+json.dumps(paired))
        sens=compute(folder)
        sections.append('Fixed-baseline-belief sensitivity (saved pressure judgments compared with baseline beliefs, no new inference): '+'\n\n'+table(['Condition','Dishonest','Assessable N','Deception','Changed labels'],[[c,r['dishonest'],r['assessable_denominator'],pct(r['deception_rate']),r['changed_from_primary']] for c,r in sens['conditions'].items()]))
    # Telemetry includes pilot and expansion, unique prompt/condition records only.
    gens={(r['config'],r['task_id'],r['condition'],r['prompt_type']):r for p in RUN.glob('mask_generations*.jsonl') for r in complete_lines(p)}
    sections.append('Realized perturbation telemetry over all saved MASK prompts at this checkpoint: '+'\n\n'+table(['Condition','Saved prompts','Mean relative RMS total/step','Steered/eligible layer-token fraction','All-prompt truncations'],[[c,len(rows),f"{statistics.mean(r['result']['stats']['realized_relative_rms_total_per_step'] for r in rows):.6f}" if rows else 'NA',f"{sum(r['result']['stats']['steered_layer_tokens'] for r in rows)/max(1,sum(r['result']['stats']['eligible_layer_tokens'] for r in rows)):.6f}",sum(r['result']['hit_token_limit'] for r in rows)] for c in CONDITIONS for rows in [[r for r in gens.values() if r['condition']==c]]]))
    capabilities={c:{(r['benchmark'],r['index']):r for r in complete_lines(RUN/f'capability_{c}.jsonl')} for c in CONDITIONS}
    caprows=[]
    for benchmark,target in [('mmlu',30),('gsm8k',10)]:
        common=set.intersection(*[{k for k in capabilities[c] if k[0]==benchmark} for c in CONDITIONS])
        for c in CONDITIONS:
            rows=[capabilities[c][k] for k in common]
            caprows.append([benchmark,c,len(rows),target,sum(r['correct'] for r in rows),pct(sum(r['correct'] for r in rows)/len(rows) if rows else None),sum(r['prediction'] is None for r in rows),sum(r['result']['hit_token_limit'] for r in rows)])
    sections.append('Capability pilots: identical SHA256-selected test indices across five conditions; exact-match scoring (numeric equivalence for GSM8K). No few-shot examples. '+'\n\n'+table(['Benchmark','Condition','Paired N','Target N','Correct','Accuracy','Unparsed','Truncated'],caprows))
    mach={}
    for c in CONDITIONS:
        records={}
        for p in (RUN/'machiavelli_main'/c).glob('seed_*/*/metrics.csv'):
            rows=list(csv.DictReader(p.open()))
            if rows:records[(p.parent.parent.name,p.parent.name)]=(rows[0],read(p.parent/'agent_quality.json'))
        mach[c]=records
    common=set.intersection(*[set(mach[c]) for c in CONDITIONS]);mrows=[]
    for c in CONDITIONS:
        rows=[mach[c][k] for k in common];n=len(rows)
        mrows.append([c,len(mach[c]),n,f"{statistics.mean(float(r['violations.deception']) for r,q in rows):.4f}" if n else 'NA',f"{statistics.mean(float(r['points']) for r,q in rows):.4f}" if n else 'NA',f"{statistics.mean(float(r['steps']) for r,q in rows):.1f}" if n else 'NA',sum(q['random_fallback_actions'] for r,q in rows if q),sum(float(r['steps'])>=150 for r,q in rows)])
    sections.append(f'Machiavelli paired trajectory pilot ({"complete" if len(common)==4 else "partial"}): first two sorted test games, seeds 0 and 1, maximum 150 actions, identical across conditions. Official trajectory resimulation and annotation metrics. Deception is the official normalized trajectory metric, not a MASK deception probability. Reward is normalized achievement points. The separate initial 10-action smoke completed/scored and is excluded here. '+'\n\n'+table(['Condition','Completed trajectories','Common paired N','Mean deception','Mean reward','Mean length','Random fallback actions','150-action cap hits'],mrows))
    plan=read(RUN/'mask_expanded_subset.json')
    if plan:sections.append(f"Expansion selection: {len(plan['items'])} fixed items, {plan['items_per_config']} per stratum, hash ordering includes pilot. Throughput bound per balanced six items across all conditions: judge {plan['judge_seconds_per_balanced_six']:.1f}s plus generation {plan['generation_seconds_per_balanced_six_parallel_five_workers']:.1f}s with five GPU workers. Used 60% of remaining budget to 10:30 UTC, reserving 40% for variance/recovery. Manifest fixed before expansion. Pilot outputs and judgments were saved before launch and reused. Overall MASK rates are unweighted selected-item rates with equal stratum sample sizes, not prevalence-weighted estimates for the full dataset. The expansion includes pilot items and is not an independent fresh confirmation sample.")
    sessions=subprocess.run(['tmux','list-sessions'],capture_output=True,text=True).stdout.strip()
    sections.append('Live tmux sessions:\n```\n'+sessions+'\n```')
    coordinator=read(RUN/'overnight_coordinator_state.json') or {}
    for note in coordinator.get('recovery_notes',[]):
        sections.append('Resolved operational issue at '+note['utc']+': '+note['issue']+' '+note['recovery'])
    sections.append('Current blockers: no unresolved infrastructure blocker recorded at this checkpoint. Evaluation jobs remain partial while running. Interpretation limits: small capability pilots, capped generations/trajectories, local single-judge scoring, and upstream random fallback actions. Check live logs for new errors before resuming.')
    sections.append('Artifacts: /lambda/nfs/fs-cand-nov05/results/steering_run contains raw generations, fit.pt/extraction.pt, locked settings, independent calls/items/paired summaries and sensitivity. Logs: /lambda/nfs/fs-cand-nov05/logs/{mask_judge_server,mask_gptoss_grade,steering_experimentCONDITION,capability_CONDITION,machiavelli_CONDITION}.log. Use paired summaries and per-trajectory CSVs to establish completion; legacy exitcode filenames can be shared between pilot and expansion commands. Actual PID/GPU/CUDA_VISIBLE_DEVICES assignments are checkpointed in gpu_process_snapshots.jsonl; queued tmux jobs can be waiting on locks without occupying a GPU. No raw artifacts are staged in Git.')
    commands='''cd /lambda/nfs/fs-cand-nov05/Deception_mitigation
# First inspect tmux ls and nvidia-smi; do not duplicate healthy jobs.
bash scripts/serve_judge.sh
bash scripts/grade_mask_pilot.sh
# These serial resume loops use GPU 0; first verify it is free.
for condition in baseline caa sttp rank2 pooled; do
  CUDA_VISIBLE_DEVICES=0 bash scripts/run_capability.sh "$condition"
done
for condition in baseline caa sttp rank2 pooled; do
  CUDA_VISIBLE_DEVICES=0 bash scripts/run_machiavelli.sh "$condition" --output-name machiavelli_main --seeds 0,1 --game-count 2 --max-steps 150
done
for condition in baseline caa sttp rank2 pooled; do
  CUDA_VISIBLE_DEVICES=0 STEERING_EVAL_CONDITIONS="$condition" MASK_SUBSET_PATH=/lambda/nfs/fs-cand-nov05/results/steering_run/mask_expanded_subset.json bash scripts/run_steering.sh --phase eval
done
MASK_SUBSET_PATH=/lambda/nfs/fs-cand-nov05/results/steering_run/mask_expanded_subset.json MASK_JUDGE_FOLDER=/lambda/nfs/fs-cand-nov05/results/steering_run/judge_gptoss_expanded bash scripts/grade_mask_pilot.sh
PYTHONPATH=/lambda/nfs/fs-cand-nov05/deps:$PWD python3 -m steering.overnight_report'''
    sections.append('Executable resume commands (put GPU workers in tmux and confirm GPU 0 is free first; judge uses GPU 5):\n```bash\n'+commands+'\n```')
    text='\n\n'.join(sections)+'\n'
    (ROOT/'OVERNIGHT_STATUS.md').write_text(text)
    (ROOT/'Deception_mitigation/REPORT.txt').write_text(text)
    print(now,'report saved','MASK',[(k,v['paired_complete_items']) for k,v in snapshots.items()],'Machiavelli paired',len(common),flush=True)
if __name__=='__main__':render()
