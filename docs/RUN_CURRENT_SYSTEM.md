# Running the current local system

The repository contains the script agent, voice service, frontend/backend,
146 published lesson pairs (91 original and 55 later pairs for Grade 3 Module 2, Grade 4 Module 1 and Grade 5 Module 1, all reviewed), the two existing supplementary Grade 3 review
pairs, and a saved real Qwen Grade 2 Module 1 Lesson 1 example. The runtime catalog
is `docs/content/lesson-pairs.json`. Paths are relative to this checkout and every
concept/assessment file is checked by SHA-256 and matched ID/version before use.
The original module collections under `ciriculam/gradeN/` still describe curriculum
coverage. Scheduling uses the next available pair within the child's grade, in
module/lesson order, and skips numbers without a pair. No old Downloads workspace
or absolute-path pair inventory is required.

> **Content status (2026-10-16):** all 148 lesson pairs are marked `reviewed` and ready for delivery by their content owner, so `--allow-draft-lessons` is not needed. The previous statuses are recorded in `docs/content/review-status-before.json`.

## Provisioning another machine

The current voice engine supports the tested Apple Silicon/macOS environment.
Use Python 3.12, Node 20.9 or newer, Postgres and Ollama. First-time installation
requires acquiring dependencies and model assets; after provisioning, the app
runs locally with Hugging Face/Transformers offline flags. Startup does not
install anything or download replacement models.

```sh
make setup
python3.12 -m venv voice_service/.venv
voice_service/.venv/bin/python -m pip install -r voice_service/requirements.txt
make db-up migrate
```

Provision the existing `qwen3.5:9b-q4_K_M` Ollama model and the Kokoro MLX
`Kokoro-82M-bf16` directory before launch. The tested voice snapshot is
`mlx-community/Kokoro-82M-bf16` revision
`a71e4d38b236d968966a2002c4c895dbd12b1c3c`; see
`docs/content/runtime-models.json` for recorded model identities. The Kokoro directory must include its
configuration, weights and `voices/af_heart.safetensors` and
`voices/am_michael.safetensors`. The current operator already has these assets;
do not redownload them. Model weights, voice assets, virtual environments,
database credentials, household/student data and audio are intentionally not
Git content. Use an existing local model directory or configure `--voice-model`.

Backend dependencies are locked in `backend/uv.lock`; frontend dependencies in
`frontend/package-lock.json`; the tested voice requirements are pinned in
`voice_service/requirements.txt`. The script agent itself needs no pip packages.
Optional assessment authoring uses its separate SymPy requirements.

## Configuration and startup

Configure `DATABASE_URL` in the process environment for your local Postgres,
or retain the existing operator runtime's `database-url.txt` outside Git.
The launcher reattaches that existing local database without replacing its data.
The backend can also read a private root `.env` when started independently;
the launcher expects `DATABASE_URL` exported in its environment. `.env.example`
contains public development defaults only.

```sh
python3 tools/verify_runtime.py
python3 tools/run_local_application.py --check
python3 tools/run_local_application.py
```

The launcher prefers `backend/.venv/bin/python` and
`voice_service/.venv/bin/python` if installed. Existing operator environments
under `~/edaptive-backend/venv` and `~/edaptive-voice/venv` still work. Override
with `--backend-python`, `--voice-python`, `--voice-model`, `--job-store`,
`--backend-runtime` or `--voice-runtime`. `--content-root` is optional and defaults
to this repository. An alternate content root must use the same portable manifest
format; script implementation is always loaded from this repository.

Open `http://127.0.0.1:3001/`. The ordinary first-run profile/PIN setup and parent
school-time setting remain unchanged. `--allow-draft-lessons` is an operator-only
evaluation flag; it does not approve the draft cards for children. Without it,
unreviewed content cannot start a scheduled class. Current questions have thinking
pauses, not answer submission, grading or mastery updates. Parent charts remain
clearly labelled sample data; consent and school-time settings are real.

For the bundled saved draft, without generating a new script:

```sh
python3 tools/run_local_application.py \
  --preview-script examples/lessons/grade2-module1-lesson1.script.json
```

Open `/lesson-preview`. This is explicit manual review with no student progress
writes. The existing `/lesson-demo` still uses an existing ready job selected
by `--demo-job-id` or the local store; it does not manufacture completed jobs.

## Verification

```sh
make check
```

This includes backend tests, module boundaries, frontend lint/typecheck/build,
script-agent/checkpoint/catalog tests and voice-service tests. Use a separate
QA Postgres database for tests, never a household database. To reuse an existing
activated backend virtualenv without installing uv, use `make check BACKEND_RUN=env`. Optional assessment arithmetic tests are documented in
`authoring/assessment/README.md`.

`tools/verify_runtime.py` checks all 148 pairs and revalidates the 84-section saved
Qwen example, exposing its 19 main-path sections for speech preparation. It makes
no model calls. `--check` additionally verifies the installed Qwen tag, Kokoro
assets and configured Python executables without running migrations or services.
