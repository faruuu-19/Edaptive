#!/usr/bin/env python3
"""One-shot comparison of the requested sample lessons; no curriculum batch or winner."""
from __future__ import annotations
import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.request import urlopen
from script_agent.benchmark import atomic_json, benchmark_one, table

MODELS = ('qwen3.5:9b-q4_K_M', 'gemma4:12b-it-q4_K_M',
          'ministral-3:8b-instruct-2512-q4_K_M', 'llama3.1:8b-instruct-q4_K_M',
          'qwen3.5:4b-q4_K_M', 'qwen3.5:4b-q8_0')

def review_pair(rows):
    """Rank complete model runs for review; style cannot override rule failures."""
    grouped={}
    for row in rows:
        grouped.setdefault(row['model'],[]).append(row)
    complete=[items for items in grouped.values()
              if {r['lesson'] for r in items}=={'area_perimeter','grade1','shape_attributes'}
              and all(r['status']=='measured' for r in items)]
    complete.sort(key=lambda items:(sum(r['final_violations'] for r in items),
                                    sum(r.get('fallback_segments',0) for r in items),
                                    -sum(r['style_score'] for r in items),items[0]['model']))
    return [next(r for r in items if r['lesson']=='area_perimeter') for items in complete[:2]]

def save_report(output,rows,waiting,finished=False):
    output=Path(output)
    atomic_json(output/'comparison.json',rows)
    pair=review_pair(rows)
    state={'finished':finished,'all_candidates_measured':bool(rows) and all(r['status']=='measured' for r in rows),'waiting_for_models':waiting,'review_pair':pair,
           'model_decision':'Pending Amna’s tone choice; no model selected.'}
    atomic_json(output/'status.json',state)
    text=table(rows)
    if waiting:text+='\nDownloads still pending: '+', '.join(waiting)+'.\n'
    if pair:
        text+='\n## Same Grade 4 lesson for human tone review\n\n'
        for r in pair:
            text+='- ['+r['model']+' — readable script]('+r['script_md']+') · [JSON]('+r['script_json']+')\n'
        text+='\nThese are review candidates ranked by remaining rule failures, then fallback use, then style. '
        text+='Flagged scripts need repair/review before delivery. Amna chooses the model.\n'
    text+='\nNo cloud calls. No files deleted. No assessment pipeline changes.\n'
    (output/'comparison.md').write_text(text)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='artifacts/script-agent/comparison')
    parser.add_argument('--rewrite',action='store_true',help='Measure the checked teacher-voice rewrite mode.')
    parser.add_argument('--wait-seconds',type=float,default=0,
                        help='Wait for the requested downloads during this one run; no recurring job.')
    args=parser.parse_args()
    samples=json.loads(Path('tests/script_fixtures/manifest.json').read_text())
    candidates={c['model']:c for c in json.loads(Path('docs/script-agent/candidates.json').read_text())}
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    sources=list(sorted(Path('script_agent').glob('*.py')))+[Path('lesson_run.py'),Path('script_agent/gold_rewrites.json'),Path('script_agent/gold_examples.json'),Path('tests/script_fixtures/manifest.json'),Path(__file__)]
    sources+=list(sorted(Path('tests/script_fixtures').glob('*.concept.json')))+list(sorted(Path('tests/script_fixtures').glob('*.assessment.json')))
    protocol=hashlib.sha256(b''.join(p.read_bytes() for p in sources)+json.dumps({'rewrite':args.rewrite,'candidates':candidates},sort_keys=True).encode()).hexdigest()
    protocol_path=output/'protocol.json'
    if protocol_path.exists() and json.loads(protocol_path.read_text())['fingerprint']!=protocol:
        parser.error('Comparison implementation or inputs changed; use a new output directory.')
    atomic_json(protocol_path,{'fingerprint':protocol,'models':list(MODELS),'curriculum_batch':False,'rewrite_enabled':args.rewrite})
    saved=output/'comparison.json'
    rows=json.loads(saved.read_text()) if saved.exists() else []
    done={(r['model'],r['lesson']) for r in rows if r['status']=='measured' or r.get('terminal')}
    # External availability failures are retried; completed model calls use their checkpoints.
    rows=[r for r in rows if r['status']=='measured' or r.get('terminal')]
    start=time.monotonic();waiting=list(MODELS)
    while True:
        try:
            with urlopen('http://127.0.0.1:11434/api/tags',timeout=10) as response:
                installed={m['name'] for m in json.load(response).get('models',[])}
        except (OSError,ValueError):installed=set()
        # If the verified official text-only artifact becomes available, include it too.
        models=list(MODELS)+(['script-ministral14b-q4'] if 'script-ministral14b-q4' in installed else [])
        for name in models:
            if name not in installed:continue
            for sample in samples:
                key=(name,sample['name'])
                if key in done:continue
                try:row=benchmark_one(sample,candidates[name],output,rewrite=args.rewrite)
                except (OSError,ValueError,RuntimeError):
                    row={'model':name,'lesson':sample['name'],'status':'not_completed',
                         'reasons':['Local server, checkpoint or resource guard interrupted. Successful calls remain checkpointed.']}
                rows=[r for r in rows if (r['model'],r['lesson'])!=key]+[row]
                if row['status']=='measured' or row.get('terminal'):done.add(key)
                save_report(output,rows,[m for m in MODELS if any((m,s['name']) not in done for s in samples)])
        waiting=[m for m in MODELS if any((m,s['name']) not in done for s in samples)]
        if not waiting or time.monotonic()-start>=args.wait_seconds:
            for name in waiting:
                for sample in samples:
                    key=(name,sample['name'])
                    if not any((r['model'],r['lesson'])==key for r in rows):
                        rows.append({'model':name,'lesson':sample['name'],'status':'not_staged',
                                     'reasons':['Requested local weights have not finished downloading. No speed, memory or style measurement exists.']})
            if 'script-ministral14b-q4' not in installed:
                for sample in samples:
                    rows.append({'model':'script-ministral14b-q4','lesson':sample['name'],
                                 'status':'not_staged','reasons':['Official publisher text-only GGUF download incomplete; no 14B result is claimed.']})
            save_report(output,rows,waiting,finished=not waiting)
            print(table(rows),flush=True)
            return 0 if not waiting and all(r['status']=='measured' for r in rows) else 3
        save_report(output,rows,waiting)
        time.sleep(30)

if __name__=='__main__':raise SystemExit(main())
