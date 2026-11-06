"""Run the official simple-evals Machiavelli entry point with a local-only model adapter.
The injected shared module supplies only the runner's provider interface, avoiding API imports.
"""
import argparse, asyncio, json, runpy, sys, types
from dataclasses import dataclass,asdict
from pathlib import Path
import torch
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
    class LocalAgent:
        def __init__(self,model=None,**kwargs):
            self.model=model or 'local/'+args.condition
            self.all_token_usage=Usage();self.max_token_usage=Usage()
        async def async_completions(self,messages,**kwargs):
            result,_=generate(model,tokenizer,layers,fit,messages,locked['settings'][args.condition],max_new_tokens=256)
            usage=Usage(input_tokens=len(tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,enable_thinking=False,return_dict=False)),output_tokens=len(result['token_ids']))
            usage.total_tokens=usage.input_tokens+usage.output_tokens
            self.all_token_usage=sum_usage([self.all_token_usage,usage]);self.max_token_usage=max_usage([self.max_token_usage,usage])
            with telemetry.open('a') as f:f.write(json.dumps({'condition':args.condition,'result':result,'settings_sha256':digest(RUN/'locked_settings.json')})+'\n')
            return types.SimpleNamespace(content=result['text'])
    shared=types.ModuleType('shared');shared.__path__=[]
    agents=types.ModuleType('shared.llm_agents');agents.LLMAgent=LocalAgent
    shared.get_llm_agent_class=lambda **kw:LocalAgent(**kw)
    shared.get_agent_config=lambda name,*a,**kw:{'model':name}
    shared.sum_token_usage=sum_usage;shared.get_max_token_usage=max_usage
    sys.modules['shared']=shared;sys.modules['shared.llm_agents']=agents
    import machiavelli_eval as runner
    context={}
    OriginalAgent=runner.MachiavelliAgent
    class AuditedAgent(OriginalAgent):
        async def run_env(self,env,**kwargs):
            env=await super().run_env(env,**kwargs)
            write_json(context['destination']/'agent_quality.json',{'random_fallback_actions':self.random_actions,'decision_steps':self.trajectory_length,'max_steps':args.max_steps,'seed':context['seed'],'game':env.game})
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
                context.update(destination=destination,seed=seed)
                destination.mkdir(parents=True,exist_ok=True)
                if (destination/'metrics.csv').exists():continue
                if not (destination/'trajectory.pkl').exists():
                    await runner.run_single_game(game,'local/'+args.condition,{'model':'local/'+args.condition},destination,max_traj_length=args.max_steps)
                df=runner.load_results(str(destination))
                runner.print_evaluation_results(df,str(destination/'metrics.csv'))
                print('SCORED MACHIAVELLI',args.condition,seed,game,flush=True)
    asyncio.run(run())

if __name__=='__main__':main()
