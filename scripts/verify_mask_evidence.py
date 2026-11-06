"""Recompute pinned MASK aggregation and audit prompt/response/judge provenance."""
import argparse,ast,collections,hashlib,itertools,json,sys,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);a=p.parse_args();root=a.package.resolve();sys.path.insert(0,str(root/'experiments/code'))
from datasets import load_from_disk
from steering import official_mask
from scripts.submission_tables import lines,latest,C
with tempfile.TemporaryDirectory() as directory:
 temporary=Path(directory);(temporary/'repos').mkdir();(temporary/'repos/mask').symlink_to(root/'experiments/upstream/mask',target_is_directory=True);official_mask.ROOT=temporary;official=official_mask.load_official()
def canonical_numeric(value):
 tree=ast.parse(value,mode='eval')
 class Infinity(ast.NodeTransformer):
  def visit_Name(self,node):
   if node.id=='inf':return ast.copy_location(ast.Constant(float('inf')),node)
   return node
 return set(map(tuple,ast.literal_eval(Infinity().visit(tree))))
run=root/'experiments/results/steering_run';manifest=json.loads((run/'mask_full_test_manifest.json').read_text())['items']
source={}
for config in sorted({r['config'] for r in manifest}):
 source.update({(config,str(r['task_id'])):r for r in load_from_disk(str(root/'data/cais__MASK'/config/'test'))})
assert all((r['config'],r['task_id']) in source for r in manifest)
generations={}
for path in sorted(run.glob('mask_generations*.jsonl')):
 for r in lines(path):
  key=tuple(r[k] for k in ['config','task_id','condition','prompt_type'])
  if key in generations:assert generations[key]['result']['token_ids']==r['result']['token_ids'] and generations[key]['messages']==r['messages'],'conflicting generation journals'
  generations[key]=r
cp=root/'experiments/results/cp_exploratory'
for r in lines(cp/'pilot_generations.jsonl'):
 generations[tuple(r[k] for k in ['config','task_id','condition','prompt_type'])]=r
lock=hashlib.sha256((root/'model/locked_settings.json').read_bytes()).hexdigest();reports={}
for folder,journal,call_path in [('judge_gptoss_expanded',run/'judge_gptoss_expanded/items.jsonl',run/'judge_gptoss_expanded/calls.jsonl'),('judge_gptoss_full',run/'judge_gptoss_full/items.jsonl',run/'judge_gptoss_full/calls.jsonl'),('cp_exploratory',cp/'pilot_judgments.jsonl',cp/'judge/calls.jsonl')]:
 calls={r['request_id']:r for r in lines(call_path)};checked=0;prompt_count=0;order_changes=0;reaggregation_changes=collections.Counter();order_sensitive=collections.Counter();order_sensitive_examples=[]
 for key,r in latest(journal).items():
  if r['status']!='complete':continue
  row=source[key[:2]];scoring=dict(r['scoring_inputs']);numeric=official['parse_proposition'](row['proposition'])[0]=='numerical'
  assert scoring['ground_truth_extracted']==row['formatted_ground_truth']
  needed=['pressured']+['belief_'+str(i) for i in [1,2,3] if row.get('belief_elicit_'+str(i))]
  requests=[calls[i] for i in r['request_ids']]
  assert requests and all(c['status']=='ok' for c in requests)
  for call in requests:
   status,parsed,_=official_mask.classify_response(call['response'],call['numeric'],official)
   assert status=='ok' and json.dumps(parsed)==json.dumps(call['parsed']),'saved judge response/parser mismatch'
  for kind in needed:
   g=generations[key+(kind,)];assert g['settings_sha256']==lock
   text=g['result']['text'];assert any(text in c['request']['messages'][-1]['content'] for c in requests),'generation absent from judge prompts'
   prompt_count+=1
  columns=['eval_belief_elicit_'+str(i) for i in [1,2,3] if row.get('belief_elicit_'+str(i))]
  if columns:
   belief=official['aggregate_eval_beliefs_statistics' if numeric else 'aggregate_eval_beliefs'](scoring,columns)
   equal=canonical_numeric(belief)==canonical_numeric(scoring['eval_belief']) if numeric else belief==scoring['eval_belief']
   assert equal,('saved belief aggregation mismatch',key,repr(belief),repr(scoring['eval_belief']),scoring)
   if numeric and belief!=scoring['eval_belief']:
    order_changes+=1
    alternative=dict(scoring,eval_belief=belief)
    alternative_honesty=int(official['aggregate_eval_honesty_statistics'](alternative,['pressure'],'eval_belief'))
    if alternative_honesty!=r['honesty']:reaggregation_changes[r['condition']]+=1
  if numeric and columns:
   alternatives={int(official['aggregate_eval_honesty_statistics'](dict(scoring,eval_belief=str(list(order))),['pressure'],'eval_belief')) for order in itertools.permutations(canonical_numeric(scoring['eval_belief']))}
   if len(alternatives)>1:
    order_sensitive[r['condition']]+=1
    order_sensitive_examples.append({'config':key[0],'task_id':key[1],'condition':key[2],'saved_honesty':r['honesty'],'possible_honesty_by_interval_order':sorted(alternatives)})
  honesty=official['aggregate_eval_honesty_statistics' if numeric else 'aggregate_eval_honesty'](scoring,['pressure'],'eval_belief')
  assert int(honesty)==r['honesty'],'saved honesty aggregation mismatch'
  checked+=1
 reports[folder]={'journal_sha256':hashlib.sha256(journal.read_bytes()).hexdigest(),'verified_condition_items':checked,'verified_prompt_records':prompt_count,'official_aggregation':'passed','saved_judge_response_parsing':'passed','generation_to_judge_prompt_linkage':'passed','numeric_list_order_changes_on_reaggregation':order_changes,'numeric_honesty_changes_if_reaggregated':dict(reaggregation_changes),'numeric_items_with_order_sensitive_honesty':dict(order_sensitive),'numeric_order_sensitive_examples':order_sensitive_examples,'numeric_note':'Pinned upstream aggregation serializes a Python set; infinity fallback parsing can depend on tuple order. Primary reproduction preserves exact saved scoring inputs; diagnostic reaggregation never overwrites labels.'}
output=root/'experiments/mask_evidence_verification.json';output.write_text(json.dumps({'status':'passed','checks':reports},indent=2)+'\n');print(output.read_text())
