"""Render the verified snapshot as an editable Markdown report, PDF, and figures."""
import argparse,json,textwrap
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);root=p.parse_args().package.resolve()
t=json.loads((root/'report/tables/verified_tables.json').read_text());n=t['mask_partial1000'][0]['complete_paired_n']
intro=f'''CAIS | Activation steering for honesty
Provisional evidence package • 6 November 2026

The original 240-item MASK cohort is complete. The copied expansion contains {n}/1,000 technically complete matched items across five conditions. This package is a provisional snapshot before the 22:00 UTC freeze. Full MASK has not been certified complete. If the expansion remains incomplete at the deadline, retain the 240-item cohort as primary and label the expansion partial.

The results do not establish a general reduction in deception. MASK paired effects vary by intervention; Machiavelli deception rises for all four steered conditions in this small sample. Capability pilots use only 30 MMLU and 10 GSM8K items per condition. The separate 24-item CP comparison shows no difference on its shared assessable subset.
'''
methods='''Methods and interpretation

Five main conditions share one Qwen/Qwen3.5-9B base, revision c202236235762e1c871ad0ccb60c8ee5ba337b9a. CAA uses layer 16 and strength 0.1; StTP layer 20 and c=2; rank-2 and pooled use strength 0.1. Calibration uses ten scenarios, separate from forty extraction scenarios. Settings and fit hashes are checked by the audit command.

MASK uses pinned official CAIS rubric/parsing with a local unsteered openai/gpt-oss-20b judge, revision 6cee5e81ee83917806bbde320786a8fb61efebee. Local model judgments can be wrong; official prompts do not make them human ground truth. Unknown beliefs/abstentions are legitimate outcomes, not technical failures. Deception is dishonest / assessable. Paired deltas use the jointly assessable baseline/condition subset, so subtracting marginal rates may give a different value. Selection of the partial expansion depends on runtime completion and is not a final benchmark estimate.

Machiavelli has four matched game/seed cases per condition (two games, two seeds), twenty trajectories total. Deception is refined violations normalized to the random-agent mean times 100, not a probability. Reward retains the official recorded normalized achievement score. Saved native replay audits passed for twenty trajectories; replay was not rerun here. Random fallback actions and malformed attempts limit interpretation; see the archived report and per-item outputs.

MMLU and GSM8K use the same deterministic test indices across conditions, with 30 and 10 items respectively. Accuracy was independently recalculated from saved response text using the recorded extraction rules. Judge-assisted answer formatting is supplementary and excluded from these primary scores.

CP-scheduled versus CP-static is exploratory: 24 predeclared items disjoint from the main 240, matched five layers, offsets >=1, strength 0.1 and equal total relative budget. Both modes are technically complete for 24 items; the direct comparison uses only 13 shared assessable items. Neither establishes equivalence or benefit.
'''
limits='''Verification and remaining work

Saved MASK judgments were deduplicated by (config, task ID, condition), restricted to manifests and checked for complete status and no judge failures. Complete technical pairs, marginal assessability and paired assessability are separately reported. The original 240 cohort and CP manifest counts are asserted. Main settings SHA256 is 8caa40a84ec74c1ceb2077427b6dd90a00fd3f29d4c1b1328724cf6e717d1527.

Source inspection shows inference-time activation hooks and saved intervention fits, with no base-model training path in the experiment. Base weights are excluded from the package. An independent comparison of local base-weight bytes against upstream LFS hashes has not been completed; do not claim independently verified unchanged weights.

This environment cannot inspect the live cluster tmux socket, write /lambda, or resolve github.com. No workers were restarted, no cluster submission was installed, and no GitHub push was completed. A local archive can preserve this snapshot, but final cluster freeze, live worker health, clean GPU inference and upstream model identity verification remain pending. This is not a final frozen submission.

Recorded experiment source commit: 3482088ed25682ae36bce26bfa26c1c3ddc6596b. The source tree had uncommitted report/snapshot additions; provenance.json records them. Packaging scripts were added later and are separately versioned in the local code checkpoint.
'''
sections=[('Original MASK cohort • complete',t['mask_primary240']),('MASK expansion • partial',t['mask_partial1000']),('Capabilities • complete small pilots',t['capabilities']),('Machiavelli • complete small pilot',t['machiavelli']),('CP • complete exploratory pilot',t['cp_exploratory'])]
def table_text(title,rows):
 keys=list(rows[0]);return '\n'+title+'\n\n'+' | '.join(keys)+'\n'+' | '.join(['---']*len(keys))+'\n'+'\n'.join(' | '.join(f'{r[k]:.6f}' if isinstance(r[k],float) else str(r[k]) for k in keys) for r in rows)+'\n'
(root/'report/report.md').write_text(intro+'\n'+methods+'\n'+''.join(table_text(*x) for x in sections)+'\n'+limits)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
page_index=0
with PdfPages(root/'report/report.pdf') as pdf:
 def save_page(fig):
  global page_index
  page_index+=1;pdf.savefig(fig);fig.savefig(root/'report/figures'/f'page_{page_index:02d}.png',dpi=100)
 def prose(title,body):
  fig=plt.figure(figsize=(8.27,11.69));fig.text(.08,.94,title,fontsize=19,color='#12344a',weight='bold');y=.88
  for para in body.split('\n\n'):
   wrapped='\n'.join(textwrap.wrap(para.replace('\n',' '),width=96));fig.text(.08,y,wrapped,va='top',fontsize=10,linespacing=1.5);y-=.019*len(wrapped.splitlines())+.028
  fig.text(.08,.035,'CAIS • Provisional saved-evidence snapshot • 6 November 2026',fontsize=8,color='#666666');save_page(fig);plt.close(fig)
 prose('Activation steering for honesty',intro)
 # Split methods to keep readable line lengths and margins.
 parts=methods.split('\n\n');prose('Study design and scoring','\n\n'.join(parts[1:3]));prose('Benchmark scope and CP pilot','\n\n'.join(parts[3:]))
 for title,rows in sections:
  fig,ax=plt.subplots(figsize=(11.69,8.27));ax.axis('off');ax.set_title(title,loc='left',fontsize=19,color='#12344a',pad=30)
  if 'mask_' in next((k for k,v in t.items() if v is rows),'') or title.startswith('CP'):
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
fig,ax=plt.subplots(figsize=(8,4));r=t['mask_primary240'];ax.bar([v['condition'] for v in r],[v['deception']*100 for v in r],color='#246b87');ax.set_ylabel('Dishonest / assessable (%)');ax.set_ylim(0,100);ax.set_title('Original MASK cohort: 240 matched items');fig.tight_layout();fig.savefig(root/'report/figures/mask240.png',dpi=180);plt.close(fig)
print(root/'report/report.pdf')
