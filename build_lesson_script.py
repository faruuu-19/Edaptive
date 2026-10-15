#!/usr/bin/env python3
"""Generate one lesson without changing assessment cards. Local inference only."""
from __future__ import annotations
import argparse
import hashlib
import json
import time
from pathlib import Path
from script_agent import plan_lesson,generate_lesson,write_lesson
from script_agent.models import LocalModel,FakeModel
from script_agent.sample_inputs import load_card
from script_agent.resources import snapshot,guard
from script_agent.benchmark import identity
from lesson_run import PressureTolerance,Checkpoint

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('concept');p.add_argument('assessment');p.add_argument('--concept-id');p.add_argument('--assessment-id')
    p.add_argument('--output',default='artifacts/script-agent/scripts');p.add_argument('--model');p.add_argument('--backend',choices=['ollama','mlx','llama.cpp'],default='ollama');p.add_argument('--endpoint')
    p.add_argument('--metaphor',choices=['detectives','builders','explorers'],default='detectives');p.add_argument('--plan-only',action='store_true');p.add_argument('--fake',action='store_true',help='Canned test output, never a benchmark.')
    p.add_argument('--weight-gb',type=float,help='Actual on-disk model weight size in decimal GB; required for live inference.')
    p.add_argument('--rewrite',action='store_true',help='Let the model rewrite teaching passages in teacher voice; code verifies numbers, equations and key terms and falls back to the card text.')
    p.add_argument('--outline',help='Reviewed JSON mapping explanation ids to worked-example source ids.')
    args=p.parse_args();c=load_card(args.concept,args.concept_id);a=load_card(args.assessment,args.assessment_id,True)
    outline=json.loads(Path(args.outline).read_text()) if args.outline else None
    plan=plan_lesson(c,a,args.metaphor,outline,rewrite=args.rewrite)
    if args.plan_only:
        print(json.dumps({k:v for k,v in plan.items() if k!='source_cards'},ensure_ascii=False,indent=2));return 0
    if args.fake:model=FakeModel()
    else:
        if not args.model or args.weight_gb is None:p.error('--model and --weight-gb are required for live inference')
        model=LocalModel(args.model,args.backend,args.endpoint)
        before=snapshot();weight_bytes=args.weight_gb*1e9
        if args.backend=='ollama':
            try:installed=identity(model)
            except (OSError,ValueError):installed=None
            if installed is None:print(json.dumps({'blocked':['Requested local model is not installed or the local server is unavailable.']}));return 3
            weight_bytes=installed['size']
        problems=guard(before,weight_bytes)
        if problems:print(json.dumps({'blocked':problems},indent=2));return 3
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    sources=b''.join(p.read_bytes() for p in sorted(Path(__file__).with_name('script_agent').glob('*.py')))+Path(__file__).with_name('script_agent').joinpath('gold_examples.json').read_bytes()+Path(__file__).with_name('script_agent').joinpath('gold_rewrites.json').read_bytes()
    fingerprint=hashlib.sha256(json.dumps(plan['segments'],sort_keys=True,ensure_ascii=False).encode()+json.dumps(installed if not args.fake and args.backend=='ollama' else {'model':args.model or 'fake','backend':args.backend,'endpoint':args.endpoint},sort_keys=True).encode()+sources).hexdigest()
    checkpoint=Checkpoint(out/(plan['concept_id']+'.checkpoint.json'),fingerprint)
    if checkpoint.cache:print('Resuming: %d finished segments reused from checkpoint.'%len(checkpoint.cache),flush=True)
    tolerance=PressureTolerance()
    def progress(s):
        if not any('model_call_failed' in a['errors'] for a in s['attempts_log']):checkpoint.add(s)
        print(s['id'],s['phase'],s['status'],flush=True)
        if isinstance(model,LocalModel):
            current=snapshot();issues=guard(current,weight_bytes,current_model_loaded=True)
            fatal=tolerance.check(issues,current.get('vm_pressure_level'),time.monotonic(),current.get('swap_used_bytes'),before.get('swap_used_bytes') or 0)
            if fatal:
                print('Resource guard: '+'; '.join(fatal),flush=True)
                raise RuntimeError('Resource guard interrupted local inference.')
    try:
        result=generate_lesson(plan,model,on_segment=progress,cache=checkpoint.cache or None);paths=write_lesson(result,Path(args.output))
        for path in paths:print(path.resolve())
        print(json.dumps(result['validation'],indent=2));return 0 if result['validation']['passed'] else 2
    except RuntimeError:
        print(json.dumps({'blocked':['Resource guard interrupted local inference; model unloaded. Re-run the same command to resume from the checkpoint.']}));return 3
    finally:
        if isinstance(model,LocalModel):model.unload()

if __name__=='__main__':raise SystemExit(main())
