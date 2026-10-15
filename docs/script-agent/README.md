# Script agent

The agent now ships in this repository: `script_agent/`, `lesson_run.py` and
`build_lesson_script.py`. It uses the Python standard library and a local Ollama,
MLX-LM or llama.cpp endpoint. The scheduled application uses the already chosen
`qwen3.5:9b-q4_K_M`. It never downloads a model or calls a cloud provider.

The planner matches concept IDs and versions, creates teaching and reflection
sections, selects the three assessment questions, and preserves every hint,
follow-up, rubric reference, worked answer and fallback route. Generation uses
small section calls, bounded repairs and visible source-text fallbacks. Number,
equation, coverage, leakage, tone and route checks are heuristic checks, not a
complete proof of mathematical or teaching quality.

```sh
python3 build_lesson_script.py \
  ciriculam/grade2/lesson-wise/math_g2_m1_l1_pairs_to_ten.json \
  ciriculam/grade2/lesson-wise/math_g2_m1_l1_pairs_to_ten.assessment_card.json \
  --concept-id math_g2_m1_l1_pairs_to_ten \
  --assessment-id assess_math_g2_m1_l1_pairs_to_ten_v2 \
  --model qwen3.5:9b-q4_K_M --weight-gb 6.55082555 --rewrite \
  --output artifacts/lesson-review
```

`--plan-only` makes no model calls. Completed sections are checkpointed and
resumed with the same command. The memory guard is retained; do not lower it
to force a run through swapping. The CLI unloads its model after a run.

`delivery_policy.main_path` is the playback order. Conditional sections are
read only after an assessment runtime selects their route. The current player
speaks main-path questions and pauses for Continue; it does not grade answers.

The real Qwen Lesson 1 example is in `examples/lessons/`. Its four source-text
fallbacks are visible. `tools/verify_runtime.py` rechecks the saved example
against the bundled source plan and current rules without model calls.
Benchmark helpers and fixtures are development utilities; the Grade 4 fixture
is explicitly a hand-authored benchmark, not an approved production assessment.
