"""Resumable, sequential three-lesson benchmark. Never downloads or deletes weights."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.request import urlopen
from . import plan_lesson,generate_lesson,write_lesson
from .generator import EXAMPLES,REWRITES,SYSTEM
from .models import LocalModel
from .resources import snapshot,guard,MemorySampler
from lesson_run import PressureTolerance


def atomic_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)

def identity(model):
    if model.backend=='ollama':
        with urlopen(model.endpoint+'/api/tags',timeout=10) as r:data=json.load(r)
        return next((m for m in data.get('models',[]) if m.get('name')==model.name or m.get('model')==model.name),None)
    return {'name':model.name,'note':'External server: record exact weight hash and server launch settings separately.'}

def benchmark_one(sample,candidate,output,rewrite=False):
    model=LocalModel(candidate['model'],candidate.get('backend','ollama'),candidate.get('endpoint'));weights=identity(model)
    if weights is None:raise ValueError('Model not installed: '+candidate['model'])
    weight_bytes=weights.get('size',candidate['weight_gb']*1e9)
    before=snapshot();reasons=guard(before,weight_bytes)
    if reasons:return {'model':model.name,'lesson':sample['name'],'status':'blocked','reasons':reasons,'resources':before,'identity':weights}
    c=json.loads(Path(sample['concept']).read_text());a=json.loads(Path(sample['assessment']).read_text());plan=plan_lesson(c,a,sample.get('metaphor','detectives'),sample.get('outline'),rewrite=rewrite)
    model_slug=re.sub('[^A-Za-z0-9_-]+','_',model.name);folder=Path(output)/model_slug/sample['name'];folder.mkdir(parents=True,exist_ok=True);checkpoint=folder/'checkpoint.json'
    # Invalidate cached completions whenever inputs, engine identity, prompts or implementation change.
    sources=b''.join(p.read_bytes() for p in sorted(Path(__file__).parent.glob('*.py')))
    digest=hashlib.sha256((json.dumps(plan,sort_keys=True)+json.dumps(weights,sort_keys=True)+SYSTEM).encode()+EXAMPLES.read_bytes()+REWRITES.read_bytes()+sources+Path('lesson_run.py').read_bytes()).hexdigest()
    saved=json.loads(checkpoint.read_text()) if checkpoint.exists() else {'fingerprint':digest,'segments':{},'calls':[],'elapsed_seconds':0,'memory_runs':[]}
    if saved['fingerprint']!=digest:raise ValueError('Checkpoint fingerprint changed; use a new output directory.')
    cache=saved['segments'];start=time.monotonic();initial_elapsed=saved['elapsed_seconds']
    initial_calls=len(saved['calls']);metrics_start=0
    tolerance=PressureTolerance()
    def progress(s):
        nonlocal metrics_start
        saved['segments'][s['id']]=s;saved['calls']+=model.metrics[metrics_start:];metrics_start=len(model.metrics)
        saved['elapsed_seconds']=initial_elapsed+time.monotonic()-start
        atomic_json(checkpoint,saved)
        print(model.name,sample['name'],s['id'],s['status'],flush=True)
        current=snapshot();issues=guard(current,weight_bytes,current_model_loaded=True)
        fatal=tolerance.check(issues,current.get('vm_pressure_level'),time.monotonic(),current.get('swap_used_bytes'),before.get('swap_used_bytes') or 0)
        if fatal:raise RuntimeError('Resource guard: '+'; '.join(fatal))
    sampler=MemorySampler(model.endpoint,model.backend)
    try:
        with sampler:result=generate_lesson(plan,model,on_segment=progress,cache=cache)
    finally:
        sampler_peaks=sampler.peaks();saved['memory_runs'].append(sampler_peaks);atomic_json(checkpoint,saved);model.unload()
    calls=saved['calls'];output_tokens=sum(m.get('output_tokens') or 0 for m in calls);decode=sum(m.get('decode_seconds') or 0 for m in calls)
    result['metrics'].update({'lesson_wall_seconds':saved['elapsed_seconds'],'model_calls':len(calls),'calls':calls,'resumed':initial_calls>0,'decode_tokens_per_second':output_tokens/decode if decode else None,'output_tokens':output_tokens,'peak_memory':{key:max((r[key] for r in saved['memory_runs'] if r[key] is not None),default=None) for key in sampler_peaks},'resources_before':before,'resources_after':snapshot(),'model_identity':weights})
    result['metrics']['memory_pressure_blips']=tolerance.blips
    paths=write_lesson(result,folder)
    return {'model':model.name,'backend':model.backend,'lesson':sample['name'],'status':'not_completed' if any('model_call_failed' in s['errors'] for s in result['segments']) else 'measured','terminal':any('model_call_failed' in s['errors'] for s in result['segments']),'tokens_per_second':result['metrics']['decode_tokens_per_second'],'seconds':result['metrics']['lesson_wall_seconds'],'peak_memory':result['metrics']['peak_memory'],'initial_violations':result['validation']['initial_rule_violations'],'final_violations':result['validation']['final_rule_violations'],'style_score':result['validation']['style']['score'],'model_calls':len(calls),'resumed':initial_calls>0,'rewrite_enabled':rewrite,'rewritten_segments':result['validation']['rewrite']['rewritten'],'fallback_segments':len(result['validation']['rewrite']['fallback_framed'])+len(result['validation']['rewrite']['fallback_verbatim']),'script_json':str(paths[0].resolve()),'script_md':str(paths[1].resolve())}

def table(rows):
    lines=['| Model | Lesson | Decode tok/s | Seconds/lesson | Server RSS GiB* | Model allocation GiB* | Initial/final violations | Style /100 | Rewritten/fallback | Calls | Status |','|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    def fmt(value):return '—' if value is None else '%.2f'%value
    for row in rows:
        mem=row.get('peak_memory',{});rss=mem.get('server_rss_bytes');alloc=mem.get('ollama_model_allocated_bytes')
        lines.append('| '+' | '.join([row['model'],row['lesson'],fmt(row.get('tokens_per_second')),fmt(row.get('seconds')),fmt(rss/1024**3 if rss is not None else None),fmt(alloc/1024**3 if alloc is not None else None),str(row.get('initial_violations','—'))+'/'+str(row.get('final_violations','—')),fmt(row.get('style_score')),str(row.get('rewritten_segments','—'))+'/'+str(row.get('fallback_segments','—')),str(row.get('model_calls','—')),row['status']])+' |')
    lines+=['','*RSS and provider-reported allocation are sampled separately. Neither is a complete measure of Apple unified memory. Speed is generated tokens / decode time; lesson time includes prompt processing, repairs, assembly and cold load. Null values were not measured. Style is a heuristic; human tone selection is still required.','']
    return '\n'.join(lines)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',default='tests/script_fixtures/manifest.json');p.add_argument('--candidates',default='docs/script-agent/candidates.json');p.add_argument('--models',nargs='*');p.add_argument('--output',default='artifacts/script-agent/benchmark');p.add_argument('--preflight',action='store_true');p.add_argument('--rewrite',action='store_true');args=p.parse_args()
    samples=json.loads(Path(args.manifest).read_text());candidates=json.loads(Path(args.candidates).read_text());rows=[]
    for candidate in candidates:
        if args.models and candidate['model'] not in args.models:continue
        for sample in samples:
            if args.preflight:
                resources=snapshot();reasons=guard(resources,candidate['weight_gb']*1e9)
                rows.append({'model':candidate['model'],'lesson':sample['name'],'status':'blocked' if reasons else 'not_run','reasons':reasons,'resources':resources})
            else:
                try:rows.append(benchmark_one(sample,candidate,args.output,rewrite=args.rewrite))
                except (OSError,ValueError,RuntimeError):rows.append({'model':candidate['model'],'lesson':sample['name'],'status':'not_completed','reasons':['Model missing, local server unavailable, changed checkpoint, or resource guard interrupted. See checkpoint and preflight; no provider error payload is logged.']})
            atomic_json(Path(args.output)/'comparison.json',rows);(Path(args.output)/'comparison.md').write_text(table(rows))
    print(table(rows))
    # Do not choose a winner or run a curriculum batch. User picks after reading scripts.
    return 0 if rows and all(r['status']=='measured' for r in rows) else 3

if __name__=='__main__':raise SystemExit(main())
