#!/usr/bin/env python3
"""Check all bundled pairs and recheck the saved Qwen example without inference."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from script_agent import generate_lesson, plan_lesson
from script_agent.sample_inputs import load_card
from voice_service.catalog import load_catalog
from voice_service.service import load_lesson


def verify(root=ROOT):
    catalog = load_catalog(root)
    path = root / "examples/lessons/grade2-module1-lesson1.script.json"
    script = json.loads(path.read_text())
    pair = next(row for row in catalog if row["concept_id"] == script["concept_id"])
    concept = load_card(pair["concept"], pair["concept_id"])
    assessment = load_card(pair["assessment"], pair["assessment_id"], True)
    plan = plan_lesson(concept, assessment, "detectives", rewrite=True)
    assert len(script["segments"]) == len(plan["segments"])
    for expected, actual in zip(plan["segments"], script["segments"]):
        if any(actual.get(key) != value for key, value in expected.items()):
            raise ValueError("Saved example does not match the bundled source plan.")

    class NoInference:
        name = "revalidation-only-no-model-calls"

        def generate(self, request):
            raise AssertionError("Saved-script verification must not call a model.")

    checked = generate_lesson(plan, NoInference(), cache={s["id"]: s for s in script["segments"]})
    if not checked["validation"]["passed"]:
        raise ValueError("Saved example fails the current script checks.")
    speech = load_lesson(path)
    return {"pairs": len(catalog), "saved_example_sections": len(script["segments"]),
            "main_path_sections": len(speech["segments"]), "model_calls": 0,
            "content_status": "draft; operator evaluation only"}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
