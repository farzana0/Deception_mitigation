"""Expose common-assessable denominators and rank-2/pooled discordant pairs."""
import argparse,json
from pathlib import Path
from steering.official_mask import RUN,complete_lines
from steering.grade_pilot import CONDITIONS,save

def compute(folder):
    latest={(r['config'],r['task_id'],r['condition']):r for r in complete_lines(folder/'items.jsonl')}
    valid={k:r for k,r in latest.items() if r['status']=='complete'}
    common=set.intersection(*[{k[:2] for k in valid if k[2]==c} for c in CONDITIONS])
    assessable={k for k in common if all(valid[k+(c,)]['honesty'] in [-1,1] for c in CONDITIONS)}
    result={'technically_valid_paired_denominator':len(common),'all_five_assessable_denominator':len(assessable),'all_five_assessable_conditions':{c:{'dishonest':sum(valid[k+(c,)]['honesty']==-1 for k in assessable),'denominator':len(assessable)} for c in CONDITIONS}}
    both={k for k in common if all(valid[k+(c,)]['honesty'] in [-1,1] for c in ['rank2','pooled'])}
    result['rank2_vs_pooled']={'both_assessable_denominator':len(both),'rank2_dishonest':sum(valid[k+('rank2',)]['honesty']==-1 for k in both),'pooled_dishonest':sum(valid[k+('pooled',)]['honesty']==-1 for k in both),'rank2_only_dishonest':sum(valid[k+('rank2',)]['honesty']==-1 and valid[k+('pooled',)]['honesty']==1 for k in both),'pooled_only_dishonest':sum(valid[k+('pooled',)]['honesty']==-1 and valid[k+('rank2',)]['honesty']==1 for k in both)}
    save(folder/'paired_assessable_analysis.json',result)
    return result
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,default=RUN/'judge_gptoss');args=parser.parse_args();print(json.dumps(compute(args.folder),indent=2))
