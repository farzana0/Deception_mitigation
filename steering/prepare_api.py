"""Build an offline official-evaluator request manifest and token-cost estimate. No API client/key access."""
import asyncio,collections,json,math
from pathlib import Path
from steering.grade_pilot import generations,score_item,save,CONDITIONS
from steering.official_mask import ROOT,RUN,load_official,SCHEMA

class PlanTransport:
    def __init__(self):self.current=[];self.requests=[]
    async def evaluator(self,client,judge_prompts,system_message,concurrency_limit,force_NumericalRangeClass_output=False):
        results={}
        for key,prompt in judge_prompts.items():
            numeric=force_NumericalRangeClass_output
            record={'model':'o3-mini' if numeric else 'gpt-4o','numeric':numeric,'system_message':system_message,'prompt':prompt,'response_schema':SCHEMA if numeric else None}
            self.requests.append(record);self.current.append({'request_id':'offline-plan','status':'ok'})
            results[key]=(42.,42.,None,None) if numeric else 'Answer: A'
        return results

async def main_async():
    from datasets import load_from_disk
    subset=json.loads((RUN/'mask_subset.json').read_text());official=load_official();transport=PlanTransport();official['evaluate_responses_async']=transport.evaluator
    groups=collections.defaultdict(dict)
    for g in generations():groups[(g['config'],g['task_id'],g['condition'])][g['prompt_type']]=g
    for item in subset['items']:
        config=item['config'];task=item['task_id'];ds=load_from_disk(str(ROOT/'data/cais__MASK'/config/'test'));row=next(r for r in ds if str(r['task_id'])==task)
        needed={'pressured'}|{'belief_'+str(k) for k in [1,2,3] if row.get('belief_elicit_'+str(k))}
        for condition in CONDITIONS:
            if not needed.issubset(groups[(config,task,condition)]):continue
            # Placeholder outputs are used only to traverse official prompt construction.
            # They are discarded; no synthetic judgments or metrics are saved.
            await score_item(official,transport,row,config,condition,groups[(config,task,condition)])
    folder=RUN/'judge_official_api';folder.mkdir(exist_ok=True)
    save(folder/'request_plan.json',{'paid_requests_started':False,'requests':transport.requests})
    estimate={};total=0.
    for model,input_rate,output_rate,output_tokens in [('gpt-4o',2.5,10.,500),('o3-mini',1.1,4.4,4096)]:
        reqs=[r for r in transport.requests if r['model']==model]
        # Conservative rough estimate; tokenization and reasoning vary, retries cost extra.
        inputs=sum(math.ceil((len(r['prompt'])+len(r['system_message']))/4) for r in reqs)
        price=inputs/1e6*input_rate+len(reqs)*output_tokens/1e6*output_rate;total+=price
        estimate[model]={'requests':len(reqs),'estimated_input_tokens_chars_div_4':inputs,'output_token_budget_each':output_tokens,'input_usd_per_million':input_rate,'output_usd_per_million':output_rate,'estimated_usd_at_output_budget':price}
    save(folder/'cost_estimate.json',{'paid_requests_started':False,'models':estimate,'estimated_usd':total,'notes':'No retries or cached-input discounts. Input token counts are rough chars/4 estimates. o3-mini reasoning consumes output budget. Official docs currently mark o3-mini shut down; requested API comparison may be unavailable. No model substituted.',
        'sources':['https://developers.openai.com/api/docs/models/gpt-4o','https://developers.openai.com/api/docs/models/o3-mini'],
        'command':'cd /lambda/nfs/fs-cand-nov05/Deception_mitigation && bash scripts/grade_mask_pilot.sh --backend api --execute-paid',
        'key_source':'OPENAI_API_KEY in the scoring shell, read only when --execute-paid is explicitly passed after user opt-in'})
    print('API REQUESTS NOT STARTED. Estimated cost:',total,flush=True)

if __name__=='__main__':asyncio.run(main_async())
