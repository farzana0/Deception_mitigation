"""Pinned official MASK prompt/evaluation/metric functions; local or opt-in API transport.
Only function/class definitions are loaded, avoiding the upstream import-time API client.
"""
import hashlib
import ast,asyncio,collections,importlib.util,json,math,os,re,time,urllib.request,urllib.error
from pathlib import Path
from typing import List,Tuple,Optional
from ast import literal_eval
import pandas as pd
from pydantic import BaseModel
ROOT=Path('/lambda/nfs/fs-cand-nov05');RUN=ROOT/'results/steering_run'
FIELDS=['lower_bound','upper_bound','relative_lower_bound','relative_upper_bound']
SCHEMA={'type':'object','properties':{k:{'type':['number','null']} for k in FIELDS},'required':FIELDS,'additionalProperties':False}


def load_official():
    base=ROOT/'repos/mask/mask'
    pin=json.loads((Path(__file__).resolve().parents[1]/'configs/mask_official_pin.json').read_text())
    for relative,expected in pin['files'].items():
        assert hashlib.sha256((base.parent/relative).read_bytes()).hexdigest()==expected, 'Pinned official MASK source changed: '+relative
    spec=importlib.util.spec_from_file_location('official_mask_prompts',base/'prompts/evaluation_prompts.py')
    prompts=importlib.util.module_from_spec(spec);spec.loader.exec_module(prompts)
    env={'pd':pd,'asyncio':asyncio,'os':os,'glob':None,'re':re,'Optional':Optional,'BaseModel':BaseModel,
         'collections':collections,'literal_eval':literal_eval,'List':List,'Tuple':Tuple}
    env.update({k:getattr(prompts,k) for k in dir(prompts) if k.isupper()})
    for filename in ['evaluate.py','metric.py']:
        tree=ast.parse((base/filename).read_text())
        nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(base/filename),'exec'),env)
    return env


def validate_numeric(content):
    data=json.loads(content)
    if not isinstance(data,dict) or set(data)!=set(FIELDS):raise ValueError('Numerical JSON fields do not match schema')
    for value in data.values():
        if value is not None and (type(value) not in (float,int) or not math.isfinite(value)):raise ValueError('Expected finite number or null')
    for a,b in [('lower_bound','upper_bound'),('relative_lower_bound','relative_upper_bound')]:
        if data[a] is not None and data[b] is not None and data[a]>data[b]:raise ValueError('Reversed numeric range')
    return tuple(data[k] for k in FIELDS)


def classify_response(response,numeric,official):
    choice=response['choices'][0];message=choice['message'];content=message.get('content') or ''
    finish=choice.get('finish_reason')
    if finish=='length':return 'truncated',None,content
    if message.get('refusal'):return 'judge_refusal',None,content
    try:
        parsed=validate_numeric(content) if numeric else official['extract_boxed_evaluation'](content)
        if not numeric and parsed not in ['A','B','C','D']:raise ValueError('No valid official binary label')
        return 'ok',parsed,content
    except (ValueError,TypeError,json.JSONDecodeError):return 'malformed',None,content


def complete_lines(path):
    if not path.exists():return []
    return [json.loads(l) for l in path.read_text().splitlines(keepends=True) if l.endswith('\n')]
