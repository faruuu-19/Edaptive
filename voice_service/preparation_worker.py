"""Run the existing script agent locally and emit progress from completed segments."""

import argparse
import hashlib
import json
import signal
import sys
import time
from pathlib import Path


def emit(**data):
    print(json.dumps(data), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--concept", type=Path, required=True)
    parser.add_argument("--assessment", type=Path, required=True)
    parser.add_argument("--concept-id", required=True)
    parser.add_argument("--assessment-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    sys.path.insert(0, str(args.root))
    from script_agent import plan_lesson, generate_lesson, write_lesson
    from script_agent.sample_inputs import load_card
    from script_agent.models import LocalModel
    from script_agent.resources import snapshot, guard
    from script_agent.benchmark import identity
    from lesson_run import Checkpoint, PressureTolerance

    c = load_card(args.concept, args.concept_id)
    a = load_card(args.assessment, args.assessment_id, True)
    plan = plan_lesson(c, a, "detectives", rewrite=True)
    total = len(plan["segments"])
    emit(phase="planning", percent=3, completed=0, total=total)
    model = LocalModel("qwen3.5:9b-q4_K_M")
    installed = identity(model)
    if not installed:
        raise ValueError("The existing local Qwen model is unavailable.")
    weight = installed["size"]
    before = snapshot()
    issues = guard(before, weight)
    if issues:
        raise ValueError("; ".join(issues))
    args.output.mkdir(parents=True, exist_ok=True)
    code = b"".join(
        p.read_bytes() for p in sorted((args.root / "script_agent").glob("*.py"))
    )
    fingerprint = hashlib.sha256(
        json.dumps(plan["segments"], sort_keys=True).encode()
        + code
        + args.concept.read_bytes()
        + args.assessment.read_bytes()
        + (args.root / "script_agent/gold_examples.json").read_bytes()
        + (args.root / "script_agent/gold_rewrites.json").read_bytes()
        + b"qwen3.5:9b-q4_K_M"
    ).hexdigest()
    checkpoint = Checkpoint(args.output / "preparation.checkpoint.json", fingerprint)
    tolerance = PressureTolerance()
    completed = 0

    def progress(segment):
        nonlocal completed
        completed += 1
        checkpoint.add(segment)
        emit(
            phase="generating",
            completed=completed,
            total=total,
            percent=3 + int(90 * completed / total),
        )
        now = snapshot()
        fatal = tolerance.check(
            guard(now, weight, current_model_loaded=True),
            now.get("vm_pressure_level"),
            time.monotonic(),
            now.get("swap_used_bytes"),
            before.get("swap_used_bytes") or 0,
        )
        if fatal:
            raise RuntimeError("; ".join(fatal))

    try:
        result = generate_lesson(
            plan, model, on_segment=progress, cache=checkpoint.cache or None
        )
        if not result["validation"]["passed"]:
            write_lesson(result, args.output / "flagged-before-repair")
        for round_no in range(2):
            bad = {s["id"]: s for s in result["segments"] if s["errors"]}
            if not bad or result["validation"]["passed"]:
                break
            valid_cache = {
                s["id"]: {"template": s["template"], "attempts_log": s["attempts_log"]}
                for s in result["segments"]
                if s["id"] not in bad
            }

            class RepairModel:
                name = model.name
                metrics = model.metrics

                def generate(self, request):
                    request = dict(request)
                    if request["segment"]["id"] in bad:
                        body = json.loads(request["prompt"])
                        previous = bad[request["segment"]["id"]]
                        body.update(
                            repair_errors=previous["errors"],
                            previous_rejected_template=previous["template"],
                            repair_instruction="Fix the reported errors. For framing, use one brief complete sentence, at most eight words, then <CONTENT>. Do not invite looking at clues or following clues; the protected passage already guides the student. Do not use little detective or claim an achievement. For teaching rewrites, preserve every protected fact and equation.",
                        )
                        request["prompt"] = json.dumps(body, ensure_ascii=False)
                    return model.generate(request)

            repaired = 0

            def repair_progress(segment):
                nonlocal repaired
                checkpoint.add(segment)
                if segment["id"] in bad:
                    repaired += 1
                    emit(
                        phase="repairing",
                        percent=93 + int(3 * repaired / len(bad)),
                        completed=total,
                        total=total,
                        repaired=repaired,
                        repair_total=len(bad),
                        repair_round=round_no + 1,
                    )
                now = snapshot()
                fatal = tolerance.check(
                    guard(now, weight, current_model_loaded=True),
                    now.get("vm_pressure_level"),
                    time.monotonic(),
                    now.get("swap_used_bytes"),
                    before.get("swap_used_bytes") or 0,
                )
                if fatal:
                    raise RuntimeError("; ".join(fatal))

            result = generate_lesson(
                plan, RepairModel(), on_segment=repair_progress, cache=valid_cache
            )
        if not result["validation"]["passed"]:
            write_lesson(result, args.output / "flagged-final")
            raise ValueError(
                "Script checks flagged %s issues. The class cannot start with this draft."
                % result["validation"]["final_rule_violations"]
            )
        paths = write_lesson(result, args.output)
        path = next(p for p in paths if p.suffix == ".json")
        emit(
            phase="validated",
            percent=96,
            completed=total,
            total=total,
            script=str(path.resolve()),
        )
    finally:
        model.unload()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        emit(error="Preparation cancelled.")
        sys.exit(2)
    except Exception as error:
        emit(error=str(error)[:500])
        sys.exit(1)
