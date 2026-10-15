# Assessment authoring tools

These are the existing authoring implementation, exact-arithmetic checks and
provider adapters previously held in Amna's local workspace. They are separate
from the student application and are not imported or started by lesson delivery.
The application uses the already authored, checked pairs in
`docs/content/lesson-pairs.json`.

Use Python 3.12 with `requirements.txt` installed during provisioning. For local
authoring, pass the Ollama backend explicitly:

```sh
python authoring/assessment/build_assessment_card.py \
  ciriculam/grade2/lesson-wise/math_g2_m1_l1_pairs_to_ten.json \
  --backend ollama --model qwen3.5:9b-q4_K_M \
  --output-dir artifacts/assessment-review
```

Run exact-arithmetic regressions with:

```sh
cd authoring/assessment
python -m unittest discover -s tests
```

The historical Groq/OpenAI adapters and the Groq-specific batch publisher are
preserved for provenance. They require explicit operator configuration and are
not part of the offline application or its startup. Do not use that historical
batch publisher as the current runtime catalog builder. Authoring output is a
draft and does not approve answers or teaching for children. Never commit API
keys, proposal caches, job databases, generated audio or model weights.
