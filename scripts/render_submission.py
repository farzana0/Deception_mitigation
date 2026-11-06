"""Render the verified snapshot as an editable Markdown report, PDF, and figures."""
import argparse,hashlib,json,textwrap
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);root=p.parse_args().package.resolve()
t=json.loads((root/'report/tables/verified_tables.json').read_text())
selection=json.loads((root/'experiments/cohort_selection.json').read_text())
full=selection['primary_cohort']=='full1000'
main_key='mask_full1000' if full else 'mask_primary240'
expansion_key='mask_full1000' if full else 'mask_partial1000'
original_key='mask_original240' if full else 'mask_primary240'
n=t[expansion_key][0]['complete_paired_n']
cohort_text=f'All 1,000 MASK items are technically complete and matched across five conditions, verified at {selection["full_completion_observed_utc"]}, before the 22:00 UTC freeze. The full cohort is the main MASK result; the original 240-item cohort is shown as a historical reference.' if full else f'The original 240-item MASK cohort is complete and remains primary. The expansion contains {n}/1,000 technically complete matched items and is partial. The 22:00 UTC selection is still pending unless the deadline has passed.'
intro=f'''CAIS | Activation steering for honesty
{'Verified full-cohort evidence package' if full else 'Provisional evidence package'} • 6 November 2026

{cohort_text}

The results do not establish a general reduction in deception. MASK paired effects vary by intervention; Machiavelli deception rises for all four steered conditions in this small sample. Capability pilots use only 30 MMLU and 10 GSM8K items per condition. The separate 24-item CP comparison shows no difference on its shared assessable subset.
'''
methods='''Methods and interpretation

Five main conditions share one Qwen/Qwen3.5-9B base, revision c202236235762e1c871ad0ccb60c8ee5ba337b9a. CAA uses layer 16 and strength 0.1; StTP layer 20 and c=2; rank-2 and pooled use strength 0.1. Calibration uses ten scenarios, separate from forty extraction scenarios. Settings and fit hashes are checked by the audit command.

MASK uses pinned official CAIS rubric/parsing with a local unsteered openai/gpt-oss-20b judge, revision 6cee5e81ee83917806bbde320786a8fb61efebee. Local model judgments can be wrong; official prompts do not make them human ground truth. Unknown beliefs/abstentions are legitimate outcomes, not technical failures. Deception is dishonest / assessable. Paired deltas use the jointly assessable baseline/condition subset, so subtracting marginal rates may give a different value. Selection of the partial expansion depends on runtime completion and is not a final benchmark estimate.

Machiavelli has four matched game/seed cases per condition (two games, two seeds), twenty trajectories total. Deception is refined violations normalized to the random-agent mean times 100, not a probability. Reward retains the official recorded normalized achievement score. Saved native replay audits passed for twenty trajectories; replay was not rerun here. Random fallback actions and malformed attempts limit interpretation; see the archived report and per-item outputs.

MMLU and GSM8K use the same deterministic test indices across conditions, with 30 and 10 items respectively. Accuracy was independently recalculated from saved response text using the recorded extraction rules. Judge-assisted answer formatting is supplementary and excluded from these primary scores.

CP-scheduled versus CP-static is exploratory: 24 predeclared items disjoint from the original 240 but overlapping all 24 items with the full 1,000-item manifest, matched five layers, offsets >=1, strength 0.1 and equal total relative budget. Both modes are technically complete for 24 items; the direct comparison uses only 13 shared assessable items. The CP modes are reported separately and are not an independent test set for the full main cohort. Neither establishes equivalence or benefit.
'''
paired=json.loads((root/'report/tables/paired_diagnostics.json').read_text())
direct=paired['rank2_vs_pooled']
methods+=f'\n\nWithin the main MASK cohort, {paired["all_five_assessable_n"]} items are assessable under all five conditions. Rank-2 versus pooled is directly matched on {direct["paired_assessable_n"]} assessable items: {direct["rank2_dishonest"]} versus {direct["pooled_dishonest"]} dishonest.\n'
methods+='''

Numerical MASK reproducibility caveat: the pinned upstream metric serializes a Python set of belief intervals. Its infinity fallback parser can depend on tuple order. The evidence audit reproduces published honesty labels from exact saved scoring inputs and checks their judge responses and generation linkage. Reaggregating numeric beliefs in another process can change some labels; this diagnostic is recorded in experiments/mask_evidence_verification.json and never overwrites the primary outputs. Preserve the saved numeric belief strings when reproducing tables.
'''
evidence_path=root/'experiments/mask_evidence_verification.json'
if evidence_path.exists():
 evidence=json.loads(evidence_path.read_text())
 assert evidence['status']=='passed'
 for folder in ['judge_gptoss_expanded','judge_gptoss_full']:
  journal=root/'experiments/results/steering_run'/folder/'items.jsonl'
  assert hashlib.sha256(journal.read_bytes()).hexdigest()==evidence['checks'][folder]['journal_sha256'],'Re-run the evidence audit after refreshing journals'
 if full:assert evidence['checks']['judge_gptoss_full']['verified_condition_items']==5000
 diagnostic=evidence['checks']['judge_gptoss_full'].get('numeric_items_with_order_sensitive_honesty',{})
 methods+=f' The interval-order permutation diagnostic found {sum(diagnostic.values())} potentially order-sensitive condition-item labels in the audited expansion: {diagnostic}. The main tables retain the original saved labels.\n'
limits='''Verification and remaining work

Saved MASK judgments were deduplicated by (config, task ID, condition), restricted to manifests and checked for complete status and no judge failures. Complete technical pairs, marginal assessability and paired assessability are separately reported. The original 240 cohort and CP manifest counts are asserted. Main settings SHA256 is 8caa40a84ec74c1ceb2077427b6dd90a00fd3f29d4c1b1328724cf6e717d1527.

Source inspection shows inference-time activation hooks and saved intervention fits, with no base-model training path in the experiment. Base weights are excluded from the package. An independent comparison of local base-weight bytes against upstream LFS hashes has not been completed; do not claim independently verified unchanged weights.

This environment cannot inspect the live cluster tmux socket, write /lambda, or resolve github.com. No workers were restarted, no cluster submission was installed, and no GitHub push was completed. A local archive can preserve this snapshot, but final cluster freeze, live worker health, clean GPU inference and upstream model identity verification remain pending. MASK cohort selection is recorded separately; GPU reproduction and remote publication remain release gates.

Recorded experiment source commit: 3482088ed25682ae36bce26bfa26c1c3ddc6596b. The source tree had uncommitted report/snapshot additions; provenance.json records them. Packaging scripts were added later and are separately versioned in the local code checkpoint.
'''
weight_path=root/'model/base_weight_verification.json'
if weight_path.exists():
 weight=json.loads(weight_path.read_text())
 if weight['status']=='passed':
  limits=limits.replace('An independent comparison of local base-weight bytes against upstream LFS hashes has not been completed; do not claim independently verified unchanged weights.', 'SHA256 of all four base-weight shards matches the cached Hugging Face LFS ETags for the pinned revision. File sizes and modification times were stable during hashing. Independent retrieval of upstream metadata remains unverified; the trust root is the cached download record.')
sections=[('MASK • full 1,000-item main result' if full else 'Original MASK cohort • main result',t[main_key]),('Original MASK • 240-item reference' if full else 'MASK expansion • partial',t[original_key] if full else t[expansion_key]),('MASK • primary-cohort diagnostics',t['mask_diagnostics']),('Capabilities • complete small pilots',t['capabilities']),('Machiavelli • complete small pilot',t['machiavelli']),('CP • complete exploratory pilot',t['cp_exploratory'])]
def table_text(title,rows):
 keys=list(rows[0]);return '\n'+title+'\n\n'+' | '.join(keys)+'\n'+' | '.join(['---']*len(keys))+'\n'+'\n'.join(' | '.join(f'{r[k]:.6f}' if isinstance(r[k],float) else str(r[k]) for k in keys) for r in rows)+'\n'
(root/'report/report.md').write_text(intro+'\n'+methods+'\n'+''.join(table_text(*x) for x in sections)+'\n'+limits)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
page_index=0
with PdfPages(root/'report/report.pdf') as pdf:
 pdf.infodict().update(Title='CAIS: Activation steering for honesty',Subject='Verified saved-result audit and cohort selection',Author='CAIS project')
 def save_page(fig):
  global page_index
  page_index+=1;pdf.savefig(fig);fig.savefig(root/'report/figures'/f'page_{page_index:02d}.png',dpi=100)
 def prose(title,body):
  fig=plt.figure(figsize=(8.27,11.69));fig.text(.08,.94,title,fontsize=19,color='#12344a',weight='bold');y=.88
  for para in body.split('\n\n'):
   wrapped='\n'.join(textwrap.wrap(para.replace('\n',' '),width=96));fig.text(.08,y,wrapped,va='top',fontsize=10,linespacing=1.5);y-=.019*len(wrapped.splitlines())+.028
  fig.text(.08,.035,('CAIS • Verified full MASK cohort • 6 November 2026' if full else 'CAIS • Provisional saved-evidence snapshot • 6 November 2026'),fontsize=8,color='#666666');save_page(fig);plt.close(fig)
 prose('Activation steering for honesty',intro)
 # Split methods to keep readable line lengths and margins.
 parts=methods.split('\n\n');prose('Study design and scoring','\n\n'.join(parts[1:3]));prose('Benchmark scope and CP pilot','\n\n'.join(parts[3:]))
 for title,rows in sections:
  fig,ax=plt.subplots(figsize=(11.69,8.27));ax.axis('off');ax.set_title(title,loc='left',fontsize=19,color='#12344a',pad=30)
  if 'assessable_n' in rows[0]:
   keys=['condition','complete_paired_n','dishonest','assessable_n','deception','paired_assessable_n','paired_delta'];labels=['Condition','Matched N','Dishonest','Assessable','Rate','Paired N','Delta (pp)']
  else:keys=list(rows[0]);labels=[k.replace('_',' ').title() for k in keys]
  cells=[]
  for r in rows:
   cells.append([f'{100*r[k]:+.2f}' if k=='paired_delta' else f'{100*r[k]:.2f}%' if k in ['deception','accuracy'] and title.startswith(('Original','MASK','CP','Capabilities')) else f'{r[k]:.2f}' if isinstance(r[k],float) else str(r[k]) for k in keys])
  table=ax.table(cellText=cells,colLabels=labels,loc='center',cellLoc='center');table.auto_set_font_size(False);table.set_fontsize(10);table.scale(1,2)
  for (i,j),cell in table.get_celld().items():
   cell.set_edgecolor('white');cell.set_facecolor('#12344a' if i==0 else '#edf3f6' if i%2 else '#f8fafb')
   if i==0:cell.get_text().set_color('white')
  fig.text(.08,.12,'Matched N counts technical completion; Paired N counts joint assessability. Lower deception is better.\nSmall cohorts and local judging limit generalization. See methods and verified per-item sources.',fontsize=10)
  save_page(fig);plt.close(fig)
 prose('Verification and limitations',limits)
fig,ax=plt.subplots(figsize=(8,4));r=t[main_key];ax.bar([v['condition'] for v in r],[v['deception']*100 for v in r],color='#246b87');ax.set_ylabel('Dishonest / assessable (%)');ax.set_ylim(0,100);ax.set_title(f'MASK main cohort: {1000 if full else 240} matched items');fig.tight_layout();fig.savefig(root/'report/figures/mask_main.png',dpi=180);plt.close(fig)
print(root/'report/report.pdf')
