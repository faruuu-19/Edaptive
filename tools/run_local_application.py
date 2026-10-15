#!/usr/bin/env python3
"""Launch the actual local application; no model downloads, cloud calls or seeded profiles."""
import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parents[1]
    parser.add_argument('--content-root', type=Path, default=root)
    parser.add_argument('--backend-runtime', type=Path, default=Path.home()/'edaptive-backend')
    parser.add_argument('--voice-runtime', type=Path, default=Path.home()/'edaptive-voice')
    parser.add_argument('--frontend-port', type=int, default=3001)
    parser.add_argument('--backend-python', type=Path, help='Existing backend Python 3.12 executable.')
    parser.add_argument('--voice-python', type=Path, help='Existing voice Python 3.12 executable.')
    parser.add_argument('--voice-model', type=Path, help='Installed Kokoro model directory.')
    parser.add_argument('--job-store', type=Path, help='Local job database and checkpoints.')
    parser.add_argument('--preview-script', type=Path, help='Explicit saved draft to audition on /lesson-preview.')
    parser.add_argument('--check', action='store_true', help='Check content, local runtimes and models without starting or migrating anything.')
    parser.add_argument('--allow-draft-lessons', action='store_true', help='Operator-only local evaluation: use audited draft cards; not approval for child delivery.')
    parser.add_argument('--demo-job-id', help='Existing ready job for the isolated demo page; never generates a demo script.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    backend = args.backend_python or (root/'backend/.venv/bin/python' if (root/'backend/.venv/bin/python').is_file() else args.backend_runtime/'venv/bin/python')
    voice = args.voice_python or (root/'voice_service/.venv/bin/python' if (root/'voice_service/.venv/bin/python').is_file() else args.voice_runtime/'venv/bin/python')
    model = args.voice_model or Path(os.environ.get('EDAPTIVE_KOKORO_MODEL', str(args.voice_runtime/'models/Kokoro-82M-bf16')))
    store = args.job_store or args.voice_runtime/'jobs'
    for path in [backend, voice, args.content_root/'docs/content/lesson-pairs.json', root/'script_agent', model/'config.json', model/'voices/af_heart.safetensors', model/'voices/am_michael.safetensors']:
        if not path.exists():
            raise SystemExit('Missing local dependency: '+str(path))
    sys.path.insert(0, str(root))
    from voice_service.catalog import load_catalog
    catalog = load_catalog(args.content_root)
    with urlopen('http://127.0.0.1:11434/api/tags',timeout=5) as response:
        import json
        names=[m['name'] for m in json.load(response)['models']]
        if 'qwen3.5:9b-q4_K_M' not in names:
            raise SystemExit('The existing Qwen model must be installed and Ollama running. No model is downloaded by this launcher.')
    if args.check:
        print(json.dumps({'pairs': len(catalog), 'qwen': 'installed', 'kokoro': 'local assets present', 'runtimes': 'present', 'downloads': 0}))
        return
    environment=os.environ.copy()
    connection=args.backend_runtime/'database-url.txt'
    if 'DATABASE_URL' not in environment:
        if not connection.exists():
            raise SystemExit('Set DATABASE_URL for Postgres or complete the isolated local database setup described in docs/voice/TIMETABLE_FLOW.md.')
        # Reattach the previously initialized local Postgres; it preserves all data.
        subprocess.run([str(backend),'-c', 'import pgserver,sys; from pathlib import Path; pgserver.get_server(Path(sys.argv[1]),cleanup_mode=None)', str(args.backend_runtime/"postgres")],check=True)
        environment['DATABASE_URL']=connection.read_text().strip()
    environment.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',EDAPTIVE_LESSON_WORKER='1',
                       EDAPTIVE_API_URL='http://127.0.0.1:8000',NEXT_TELEMETRY_DISABLED='1')
    demo_job = args.demo_job_id
    if not demo_job and not args.preview_script:
        import json, sqlite3
        cache = store/'jobs.sqlite3'
        if cache.exists():
            with sqlite3.connect(cache) as db:
                ready = [json.loads(row[0]) for row in db.execute('SELECT body FROM job')]
            ready = [job for job in ready if job['status']=='ready' and job['concept_id']=='math_g2_m1_l1_pairs_to_ten' and Path(job.get('script','')).is_file()]
            if ready: demo_job = max(ready, key=lambda job: job.get('finished_at',job['created_at']))['id']
    if demo_job:
        import uuid
        environment.update(EDAPTIVE_VOICE_PREVIEW='1', EDAPTIVE_DEMO_JOB_ID=str(uuid.UUID(demo_job)))
    if args.preview_script:
        from voice_service.service import load_lesson
        load_lesson(args.preview_script)
        environment['EDAPTIVE_VOICE_PREVIEW']='1'
    if args.allow_draft_lessons:
        environment['EDAPTIVE_ALLOW_DRAFT_LESSONS']='1'
    subprocess.run([str(backend),'-m','alembic','upgrade','head'],cwd=root/'backend',env=environment,check=True)
    children=[]
    def stop(*_):
        for child in reversed(children):
            if child.poll() is None:os.killpg(child.pid, signal.SIGTERM)
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        voice_command = [str(voice),'-B','-m','voice_service.service','--content-root',str(args.content_root),'--model',str(model),'--job-store',str(store)]
        if args.preview_script: voice_command += ['--script',str(args.preview_script.resolve())]
        children.append(subprocess.Popen(voice_command,cwd=root,env=environment,start_new_session=True))
        children.append(subprocess.Popen([str(backend),'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000'],cwd=root/'backend',env=environment,start_new_session=True))
        children.append(subprocess.Popen(['npm','run','dev','--','--hostname','127.0.0.1','--port',str(args.frontend_port)],cwd=root/'frontend',env=environment,start_new_session=True))
        print('Open http://127.0.0.1:%s/; set up your own household if this is the first run.'%args.frontend_port,flush=True)
        while all(child.poll() is None for child in children):time.sleep(1)
    except KeyboardInterrupt:pass
    finally:
        stop()
        for child in children:
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()


if __name__=='__main__':main()
