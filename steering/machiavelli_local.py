"""Run the official simple-evals Machiavelli entry point with a local-only model adapter.
The injected shared module supplies only the runner's provider interface, avoiding API imports.
"""
import argparse, asyncio, collections, hashlib, json, pickle, runpy, sys, types
from dataclasses import dataclass,asdict
from pathlib import Path
import torch
from steering.journal import repair_tail
from steering.official_mask import complete_lines
from steering.experiment import ROOT,RUN,load,generate,write_json,digest

@dataclass
class Usage:
    input_tokens:int=0
    output_tokens:int=0
    total_tokens:int=0
    cached_tokens:int=0
    cost:float=0.
    def model_dump(self):return asdict(self)

def sum_usage(values):return Usage(**{k:sum(getattr(v,k) for v in values) for k in Usage.__dataclass_fields__})
def max_usage(values):return Usage(**{k:max((getattr(v,k) for v in values),default=0) for k in Usage.__dataclass_fields__})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--condition',required=True,choices=['baseline','caa','sttp','rank2','pooled']);parser.add_argument('--output-name',default='machiavelli');parser.add_argument('--seeds',default='0,1');parser.add_argument('--game-count',type=int,default=2);parser.add_argument('--max-steps',type=int,default=10);args=parser.parse_args()
    assert (RUN/'locked_settings.json').exists()
    root=ROOT/'repos/simple-evals'
    sys.path.insert(0,str(root));sys.path.insert(0,str(root/'machiavelli_eval'))
    from machiavelli.config import MachiavelliConfig
    games=sorted(MachiavelliConfig().games_test)[:args.game_count]
    locked=json.loads((RUN/'locked_settings.json').read_text());fit=torch.load(RUN/'fit.pt',weights_only=False)
    model,tokenizer,layers=load()
    output=RUN/args.output_name/args.condition;output.mkdir(parents=True,exist_ok=True)
    telemetry=output/'local_generations.jsonl'
    context={}
    seeds=[int(value) for value in args.seeds.split(',')]
    replay=collections.defaultdict(list)
    repair_tail(telemetry)
    records=complete_lines(telemetry)
    legacy=[r for r in records if 'game' not in r]
    if legacy:
        from utils import extract_json_with_keys
        position=0
        for seed in seeds:
            for game in games:
                path=output/('seed_'+str(seed))/game/'trajectory.pkl'
                start=position
                if path.exists():
                    trajectory=pickle.load(path.open('rb'))
                    for action,info in zip(trajectory.action_list,trajectory.info_list):
                        for attempt in range(5):
                            if position>=len(legacy):raise ValueError('Incomplete legacy action transcript')
                            response=extract_json_with_keys(legacy[position]['result']['text']);position+=1
                            try:
                                valid=response is not None and 'reasoning' in response and 0<=int(response['action'])<info['game_state']['num_choices']
                            except (KeyError,TypeError,ValueError):valid=False
                            if valid:
                                assert int(response['action'])==action,'Legacy trajectory/action mismatch'
                                break
                    replay[seed,game].extend(legacy[start:position])
                else:
                    replay[seed,game].extend(legacy[position:]);position=len(legacy)
                    break
            if position==len(legacy):break
    for record in records:
        if 'game' in record:replay[record['seed'],record['game']].append(record)
    deterministic_cache={record['messages_sha256']:record['result'] for records in replay.values() for record in records if 'messages_sha256' in record}
    class LocalAgent:
        def __init__(self,model=None,**kwargs):
            self.model=model or 'local/'+args.condition
            self.all_token_usage=Usage();self.max_token_usage=Usage();self.call_index=0
        async def async_completions(self,messages,**kwargs):
            key=(context['seed'],context['game'])
            message_hash=hashlib.sha256(json.dumps(messages,sort_keys=True).encode()).hexdigest()
            cached=replay[key]
            if self.call_index<len(cached):
                record=cached[self.call_index]
                assert record.get('messages_sha256',message_hash)==message_hash,'Checkpoint conversation mismatch'
                result=record['result']
            else:
                if message_hash in deterministic_cache:
                    result=deterministic_cache[message_hash]
                else:
                    result,_=generate(model,tokenizer,layers,fit,messages,locked['settings'][args.condition],max_new_tokens=256)
                    deterministic_cache[message_hash]=result
                record={'condition':args.condition,'seed':context['seed'],'game':context['game'],'call_index':self.call_index,'messages_sha256':message_hash,'result':result,'settings_sha256':digest(RUN/'locked_settings.json')}
                with telemetry.open('a') as f:f.write(json.dumps(record)+'\n');f.flush()
                replay[key].append(record)
            self.call_index+=1
            usage=Usage(input_tokens=len(tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,enable_thinking=False,return_dict=False)),output_tokens=len(result['token_ids']))
            usage.total_tokens=usage.input_tokens+usage.output_tokens
            self.all_token_usage=sum_usage([self.all_token_usage,usage]);self.max_token_usage=max_usage([self.max_token_usage,usage])
            return types.SimpleNamespace(content=result['text'])
    shared=types.ModuleType('shared');shared.__path__=[]
    agents=types.ModuleType('shared.llm_agents');agents.LLMAgent=LocalAgent
    shared.get_llm_agent_class=lambda **kw:LocalAgent(**kw)
    shared.get_agent_config=lambda name,*a,**kw:{'model':name}
    shared.sum_token_usage=sum_usage;shared.get_max_token_usage=max_usage
    sys.modules['shared']=shared;sys.modules['shared.llm_agents']=agents
    import machiavelli_eval as runner
    OriginalAgent=runner.MachiavelliAgent
    class AuditedAgent(OriginalAgent):
        async def run_env(self,env,**kwargs):
            step=env.step
            def checkpointed_step(action):
                value=step(action)
                env.trajectory.save(context['destination']/'trajectory.checkpoint')
                write_json(context['destination']/'agent_checkpoint.json',{'history':self.history,'random_fallback_actions':self.random_actions,'decision_steps':self.trajectory_length})
                return value
            env.step=checkpointed_step
            env=await super().run_env(env,**kwargs)
            write_json(context['destination']/'agent_quality.json',{'random_fallback_actions':self.random_actions,'decision_steps':self.trajectory_length,'request_count':self.llm_agent.call_index,'max_steps':args.max_steps,'seed':context['seed'],'game':env.game})
            return env
    runner.MachiavelliAgent=AuditedAgent
    seeds=[int(value) for value in args.seeds.split(',')]
    write_json(output/'protocol.json',{'games':games,'max_trajectory_length':args.max_steps,'seeds':seeds,'official_runner':str(Path(runner.__file__)),'condition':args.condition,'settings_sha256':digest(RUN/'locked_settings.json')})
    original_reset=runner.MachiavelliEnv.reset
    async def run():
        for seed in seeds:
            # Upstream agent calls reset() without a seed; inject the recorded fixed seed.
            runner.MachiavelliEnv.reset=lambda self, *a, _seed=seed, **kw: original_reset(self,seed=_seed)
            for game in games:
                destination=output/('seed_'+str(seed))/game
                context.update(destination=destination,seed=seed,game=game)
                destination.mkdir(parents=True,exist_ok=True)
                if (destination/'metrics.csv').exists():continue
                if not (destination/'trajectory.pkl').exists():
                    await runner.run_single_game(game,'local/'+args.condition,{'model':'local/'+args.condition},destination,max_traj_length=args.max_steps)
                df=runner.load_results(str(destination))
                runner.print_evaluation_results(df,str(destination/'metrics.csv'))
                print('SCORED MACHIAVELLI',args.condition,seed,game,flush=True)
    asyncio.run(run())

if __name__=='__main__':main()
