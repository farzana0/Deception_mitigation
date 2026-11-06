"""Read-only result tables and Toronto freeze selection; no experiment mutations."""
import argparse,collections,datetime,json,time
from pathlib import Path
from zoneinfo import ZoneInfo
R=Path('/lambda/nfs/fs-cand-nov05');RUN=R/'results/steering_run';C=['baseline','caa','sttp','rank2','pooled'];LABEL={'baseline':'Baseline','caa':'CAA','sttp':'StTP','rank2':'Rank-2','pooled':'Pooled'}

def read(p):return json.loads(p.read_text())
def lines(p):return [json.loads(s) for s in p.read_text().splitlines(keepends=True) if s.endswith('\n')]
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])
def delta(x):return f'{x:+.2f}'
def progress():
 now=datetime.datetime.now(datetime.timezone.utc);s=read(RUN/'judge_gptoss_full/paired_summary.json');n=s['paired_complete_items']
 start=datetime.datetime(2026,11,6,9,20,41,tzinfo=datetime.timezone.utc);gain=n-240;hours=(now-start).total_seconds()/3600;rate=gain/hours if gain>0 else None
 eta=now+datetime.timedelta(hours=(1000-n)/rate) if rate else None
 return {'utc':now.isoformat(),'complete_pairs':n,'new_pairs_since_start':gain,'start_pairs':240,'expansion_started_utc':start.isoformat(),'new_paired_items_per_hour':rate,'eta_utc':eta.isoformat() if eta else None,'eta_toronto':eta.astimezone(ZoneInfo('America/Toronto')).isoformat() if eta else None}

def report(path,freeze=False):
 p=progress();full=read(RUN/'judge_gptoss_full/paired_summary.json')
 select_full=freeze and full['paired_complete_items']==1000 and all(full['conditions'][c]['complete_items']==1000 and full['conditions'][c]['technical_failures']==0 for c in C)
 folder=RUN/('judge_gptoss_full' if select_full else 'judge_gptoss_expanded');s=read(folder/'paired_summary.json');n=s['paired_complete_items']
 items={(x['config'],x['task_id'],x['condition']):x for x in lines(folder/'items.jsonl')}
 keys=set.intersection(*[{k[:2] for k,v in items.items() if k[2]==c and v['status']=='complete'} for c in C]);assert len(keys)==n
 content=[f'# Verified results snapshot — {p["utc"]}', '', 'Jobs remain running and steering settings remain locked.', '', f'Main MASK cohort: {n} complete paired items. '+('Freeze decision applied.' if freeze else 'Original completed 240-item cohort; expansion remains separate until freeze.'), '', '## MASK', '', 'Official CAIS MASK rubric/parsing/aggregation with local unsteered GPT-OSS-20B judging. Lower deception is better. Each score below uses its own assessable items; paired deltas use the baseline/condition jointly assessable intersection, so they may differ from subtracting the displayed marginal rates.', '']
 rows=[]
 for c in C:
  d=s['conditions'][c];common=[k for k in keys if items[k+(c,)]['honesty'] in [-1,1] and items[k+('baseline',)]['honesty'] in [-1,1]]
  diff=sum(int(items[k+(c,)]['honesty']==-1)-int(items[k+('baseline',)]['honesty']==-1) for k in common)/len(common)*100
  rows.append([LABEL[c],f'{d["dishonest"]}/{d["assessable_denominator"]}',f'{d["deception_rate"]*100:.2f}%',f'{diff:+.2f} pp (n={len(common)})',f'{d["dishonest"]}/{n} ({d["deception_per_all_paired_items"]*100:.2f}%)'])
 content += [table(['Condition','Dishonest/assessable','Deception','Paired delta vs baseline','Dishonest/all paired'],rows),'']
 aux=read(RUN/'judge_gptoss_response_status/paired_summary.json')
 rows=[]
 for c in C:
  d=s['conditions'][c];a=aux['conditions'][c] if not select_full else None
  rows.append([LABEL[c],f'{d["belief_coverage"]*100:.2f}%',f'{a["explicit_refusal_count"]}/{240}' if a else 'See full auxiliary coverage',f'{d["truncated_target_responses"]}/{n}',d['abstention_or_unknown_count'],d['technical_failures']])
 content += [table(['Condition','Belief coverage','Explicit refusals (judge)','Truncated pressure responses','C/no numeric claim','Technical failures'],rows),'','Refusals are independent auxiliary judge labels, not the much narrower regex counts. Unknown/abstention labels are legitimate outcomes, not technical failures. Refusal and truncation count deltas vs baseline in the 240-item cohort are: CAA 0/-12; StTP -3/-8; Rank-2 -3/-2; Pooled -3/-10. Belief coverage includes supplied references for provided_facts.','']
 common=[k for k in keys if items[k+('rank2',)]['honesty'] in [-1,1] and items[k+('pooled',)]['honesty'] in [-1,1]]
 rank=sum(items[k+('rank2',)]['honesty']==-1 for k in common);pool=sum(items[k+('pooled',)]['honesty']==-1 for k in common)
 content += [f'**Rank-2 vs pooled:** {rank}/{len(common)} ({100*rank/len(common):.2f}%) versus {pool}/{len(common)} ({100*pool/len(common):.2f}%); paired delta {100*(rank-pool)/len(common):+.2f} pp.', '', 'Fixed-baseline-belief sensitivity (same saved pressure judgments, baseline beliefs held fixed):','']
 sens=read(folder/'fixed_baseline_belief_summary.json') if (folder/'fixed_baseline_belief_summary.json').exists() else None
 if sens:
  sk=read(folder/'fixed_baseline_belief_items.json');si={(v['config'],v['task_id'],v['condition']):v for v in sk};rows=[]
  for c in C:
   d=sens['conditions'][c];same=[k for k in keys if si[k+(c,)]['honesty'] in [-1,1] and si[k+('baseline',)]['honesty'] in [-1,1]]
   diff=sum(int(si[k+(c,)]['honesty']==-1)-int(si[k+('baseline',)]['honesty']==-1) for k in same)/len(same)*100
   rows.append([LABEL[c],f'{d["dishonest"]}/{d["assessable_denominator"]}',f'{d["deception_rate"]*100:.2f}%',f'{diff:+.2f} pp (n={len(same)})',d['changed_from_primary']])
  content += [table(['Condition','Dishonest/assessable','Deception','Paired delta vs baseline','Labels changed'],rows),'']
 content += ['## Machiavelli', '', '20 total trajectories: four matched game/seed cases per condition (two games × two seeds). Deception is the official refined violation count normalized to the random-agent mean ×100, not a percentage probability. Reward is the official recorded normalized achievement-point score; trajectories were independently replay-verified.','']
 mach=read(RUN/'machiavelli_saved_output_audit.json')['conditions'];inv=read(RUN/'machiavelli_quality_v1/inventory.json');bad=read(RUN/'machiavelli_quality_v1/all_invalid_attempts.json');rows=[]
 for c in C:
  d=mach[c];irs=[x for x in inv if x['main_pilot'] and x['trajectory'].split('/')[1]==c];invalid=sum(x['invalid_attempts'] for x in irs);steps=sum(x['decisions'] for x in irs);fallback=sum(x['random_fallback_actions'] for x in irs);attempts=steps-fallback+invalid
  rows.append([LABEL[c],4,f'{d["mean_deception"]:.2f}',delta(d['mean_deception']-mach['baseline']['mean_deception']),f'{d["mean_reward"]:.2f}',delta(d['mean_reward']-mach['baseline']['mean_reward']),f'{invalid}/{attempts}',f'{fallback}/{steps}'])
 content += [table(['Condition','Paired N','Deception ↓','Paired delta','Reward ↑','Paired delta','Invalid attempts/requests','Random fallbacks/decisions'],rows),'','Invalid attempts include malformed JSON and retries; baseline additionally had five out-of-range/missing-action attempts, versus zero for the other conditions. All executed fallback actions were valid environment choices. Random-fallback count deltas vs baseline: CAA -14, StTP -3, Rank-2 -10, Pooled +17.','',f'**Rank-2 vs pooled:** deception {mach["rank2"]["mean_deception"]-mach["pooled"]["mean_deception"]:+.2f}, reward {mach["rank2"]["mean_reward"]-mach["pooled"]["mean_reward"]:+.2f}, 135 fewer invalid attempts and 27 fewer random fallbacks on the same four game/seed cases.','', 'The pinned runner records points before the final action. Replay-derived final-point means are additionally: baseline 6.90, CAA 18.61, StTP 12.99, Rank-2 11.53, pooled 19.89. The official recorded score is retained above.','', '## Capabilities — deterministic primary scores', '', 'MMLU checks broad capability; GSM8K checks mathematical reasoning. Exactly the same fixed test indices are used across all five conditions. These are small pilots, not full-benchmark estimates.','']
 cap=read(RUN/'capability_extraction_v1/summary.json')['conditions'];rows=[]
 for c in C:
  m,g=cap['mmlu'][c],cap['gsm8k'][c]
  rows.append([LABEL[c],f'{m["original_correct"]}/{m["n"]} ({100*m["original_accuracy"]:.1f}%)',f'{100*(m["original_accuracy"]-cap["mmlu"]["baseline"]["original_accuracy"]):+.1f} pp',f'{g["original_correct"]}/{g["n"]} ({100*g["original_accuracy"]:.1f}%)',f'{100*(g["original_accuracy"]-cap["gsm8k"]["baseline"]["original_accuracy"]):+.1f} pp'])
 content += [table(['Condition','MMLU accuracy','Paired delta','GSM8K accuracy','Paired delta'],rows),'','**Rank-2 vs pooled:** MMLU +3.3 pp (30 paired questions); GSM8K -10.0 pp (10 paired questions).','', 'GSM8K judge-assisted formatting checks — supplementary only:','']
 rows=[]
 for c in C:
  g=cap['gsm8k'][c];rows.append([LABEL[c],f'{g["judge_requested"]}/{g["n"]}',g['rescue'],f'{g["assisted_correct"]}/{g["n"]} ({100*g["assisted_accuracy"]:.1f}%)',f'{100*(g["assisted_accuracy"]-cap["gsm8k"]["baseline"]["assisted_accuracy"]):+.1f} pp',g['judge_failure']])
 content += [table(['Condition','Formatting checks','Recovered correct answers','Assisted accuracy','Paired delta','Judge failures'],rows),'','The extraction judge sees no gold answer, must quote an explicitly stated answer, and must not solve unfinished reasoning. Deterministic scores above are unchanged. Original GSM8K truncations: baseline/CAA/StTP 2 each, Rank-2 1, pooled 0.','', '## Quality judge controls and remaining work', '']
 for name in ['quality_mask_v1','quality_capability_v1','quality_capability_v2','capability_extraction_v1']:
  vp=RUN/name/'validation.json'
  if vp.exists():
   v=read(vp);content += [f'- {name}: **{v["status"]}**, {sum(bool(x.get("passed")) for x in v.get("cases",[]))}/{len(v.get("cases",[]))} validation cases.']
 content += ['', 'Capability v1 failed the benign-refusal control and was not used for scoring. The revised, separately versioned v2 passed. Passing these controls does not establish preserved output quality; qualitative scoring is still partial and order-swap disagreements are reported.','', '## Expansion ETA and reporting freeze', '',f'As of {p["utc"]}: {p["complete_pairs"]}/1,000 complete paired MASK items. Since 09:20:41 UTC, {p["new_pairs_since_start"]} new pairs completed: {p["new_paired_items_per_hour"]:.1f} paired items/hour. Linear extrapolation: {p["eta_utc"]} UTC / {p["eta_toronto"]} Toronto. This is provisional; strata difficulty, generation bottlenecks and concurrent quality judging can change throughput.', '', '**Freeze: 2026-11-06 17:00 America/Toronto = 22:00 UTC.** If all 1,000 items are not completely judged across all five conditions at freeze, the original 240-item cohort remains the main MASK result and expansion is labeled partial. Jobs continue; settings stay locked.','', 'No method consistently reduces deception across both MASK and Machiavelli. Small capability pilots cannot establish equivalence. Do not interpret preserved accuracy in these pilots or passed judge controls as proof of preserved general capability.']
 path.write_text('\n'.join(content)+'\n')
 return {'report':str(path),'cohort':n,'freeze':freeze,'full_complete_pairs':p['complete_pairs'],'progress':p}

def main():
 p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');a=p.parse_args()
 if a.freeze:
  deadline=datetime.datetime(2026,11,6,22,tzinfo=datetime.timezone.utc).timestamp()
  while time.time()<deadline:
   with (RUN/'freeze_progress.jsonl').open('a') as f:f.write(json.dumps(progress())+'\n')
   time.sleep(min(60,max(0,deadline-time.time())))
  result=report(R/'RESULTS_AT_FREEZE.md',True)
  (RUN/'report_freeze_decision.json').write_text(json.dumps(result,indent=2)+'\n')
 else:
  result=report(R/'RESULTS_NOW.md')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
