"""Build a draft easy/medium/hard root-question set for one concept card."""

import argparse
import json
import os
import shutil
import sys
import uuid
from pathlib import Path

from concept_card_loader import ConceptCardError, load_file
from model_backends import ModelConfigError, add_backend_args, add_fallback_args, make_client, returned_backend_labels, with_fallback
from question_generator import (PROVIDER_FAILURE_CODES, FallbackClient, GenerationConfig, ModelRequestError, OllamaClient, generate_one,
                                validate_saved_proposal)


class _NotReusable(Exception):
    """The cached easy proposal belongs to a different concept card (expected; not an error)."""


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


_OUTPUT_NAMES = tuple(f"{level}_{suffix}.json" for level in ("easy", "medium", "hard")
                      for suffix in ("proposal", "run")) + ("root_question_set.json", "run_summary.json")


def _archive_outputs(directory: Path) -> dict[Path, Path]:
    existing = [directory / name for name in _OUTPUT_NAMES if (directory / name).exists()]
    if not existing:
        return {}
    archive = directory / "previous-runs" / ("previous-run-" + uuid.uuid4().hex)
    archive.mkdir(parents=True)
    moved = {}
    for path in existing:
        if not path.is_file():
            raise OSError(f"known generator output is not a file: {path}")
        target = archive / path.name
        shutil.move(str(path), str(target))
        moved[path.resolve()] = target
    return moved


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--concept-id", help="select a card from a collection")
    parser.add_argument("--easy-proposal", type=Path, default=Path("artifacts/step2/equal_groups_proposal.json"))
    parser.add_argument("--easy-log", type=Path, default=Path("artifacts/step2/equal_groups_run.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/step3"))
    add_backend_args(parser)
    add_fallback_args(parser)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--max-output-tokens", type=int, default=1024)
    parser.add_argument("--repairs", type=int, choices=(0, 1), default=1)
    args = parser.parse_args()
    try:
        cards = load_file(args.file)
        if args.concept_id:
            cards = [card for card in cards if card.concept_id == args.concept_id]
        if len(cards) != 1:
            parser.error(f"expected one concept card, found {len(cards)}; use --concept-id")
        card = cards[0]
        config = GenerationConfig(timeout=args.timeout, max_output_tokens=args.max_output_tokens,
                                  max_repair_requests=args.repairs)
    except (ConceptCardError, ValueError) as exc:
        parser.error(str(exc))

    try:
        client = make_client(args, OllamaClient)  # missing key fails before any file is written
        if args.list_models:
            if args.backend not in ("groq", "openai"):
                parser.error("--list-models applies to the groq or openai backend only")
            print("\n".join(client.list_models()))
            return 0
        client = with_fallback(client, args, OllamaClient)
    except (ModelConfigError, ModelRequestError, TimeoutError) as exc:
        parser.error(str(exc))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    moved = _archive_outputs(args.output_dir)
    # A user may explicitly reuse a current output that has just been archived.
    args.easy_proposal = moved.get(args.easy_proposal.resolve(), args.easy_proposal)
    args.easy_log = moved.get(args.easy_log.resolve(), args.easy_log)
    run_id = "run_" + uuid.uuid4().hex

    def write_current(path: Path, value: dict) -> None:
        _write(path, {**value, "run_id": run_id})

    proposals = {}
    timings = {}
    errors = {}
    notes = {}
    provider_failure = None
    levels = {}

    # Reuse only a saved easy proposal that passes current validation and linkage.
    if args.easy_proposal.is_file():
        try:
            saved = json.loads(args.easy_proposal.read_text(encoding="utf-8"))
            if not isinstance(saved, dict):
                raise ValueError("saved easy proposal must be an object")
            if isinstance(saved, dict) and (saved.get("concept_id"), saved.get("concept_version")) != (
                    card.concept_id, card.card_version):
                # A cached easy question for some other card is expected, not a failure: just generate a new one.
                notes["easy_reuse"] = (f"saved easy proposal is for {saved.get('concept_id')} v{saved.get('concept_version')}, "
                                       f"not this card; a new easy question is generated")
                raise _NotReusable()
            if saved.get("difficulty") != "easy":
                raise ValueError("saved easy proposal has a different difficulty")
            proposals["easy"] = validate_saved_proposal(saved, card, config)
            proposals["easy"]["served_by"] = "reused_saved_proposal"
            proposals["easy"].update(run_id=run_id, status="reused")
            write_current(args.output_dir / "easy_proposal.json", proposals["easy"])
            levels["easy"] = {"status": "reused"}
            timings["easy"] = {"reused": True, "elapsed_seconds": None, "source": str(args.easy_proposal)}
            if args.easy_log.is_file():
                try:
                    prior = json.loads(args.easy_log.read_text(encoding="utf-8"))
                    if not isinstance(prior, dict) or not isinstance(prior.get("result"), dict):
                        raise ValueError("optional easy log and its result must be objects")
                    timings["easy"].update(elapsed_seconds=prior["result"].get("elapsed_seconds"), source=str(args.easy_log))
                except (ValueError, OSError, TypeError) as exc:
                    notes["easy_log"] = f"optional source log unavailable; easy remains reused: {exc}"
            write_current(args.output_dir / "easy_run.json", {
                "status": "reused", "difficulty": "easy", "source_proposal": str(args.easy_proposal),
                "source_log": str(args.easy_log) if args.easy_log.is_file() else None,
                "served_by": "reused_saved_proposal", "served_by_attempts": [],
                "result": {"proposal": proposals["easy"], "error": None, "attempts": [], "elapsed_seconds": None}})
        except _NotReusable:
            pass
        except (ValueError, OSError, TypeError) as exc:
            errors["easy_reuse"] = str(exc)

    for difficulty in ("easy", "medium", "hard"):
        if difficulty in proposals:
            continue
        # Each level is checked against every already-accepted (or reused) proposal, easy first.
        distinct_from = [proposals[level] for level in ("easy", "medium") if level in proposals and level != difficulty]
        if provider_failure:
            # The provider itself is unusable (daily quota with fallback off, bad key, unreachable): trying the next
            # level would only repeat the same failed request, so stop asking it for the rest of this run.
            errors[difficulty] = f"{difficulty} not attempted: the provider failed earlier in this run ({provider_failure})"
            levels[difficulty] = {"status": "skipped"}
            skipped = {"code": "skipped_provider_failure", "message": errors[difficulty]}
            write_current(args.output_dir / f"{difficulty}_proposal.json",
                          {"status": "skipped", "proposal": None, "error": skipped})
            write_current(args.output_dir / f"{difficulty}_run.json", {
                "status": "skipped", "difficulty": difficulty, "served_by": None, "served_by_attempts": [],
                "result": {"proposal": None, "error": skipped, "attempts": [], "elapsed_seconds": None}})
            timings[difficulty] = {"reused": False, "elapsed_seconds": None, "attempts": 0, "status": "skipped"}
            continue
        result = generate_one(card, client, config, difficulty=difficulty, distinct_from=distinct_from)
        status = "accepted" if result.proposal is not None else "failed"
        levels[difficulty] = {"status": status}
        if result.proposal is not None:
            result.proposal.update(run_id=run_id, status=status)
        if difficulty == "hard" and "medium" not in proposals:
            compared = (result.proposal or {}).get("verification", {}).get("distinctness_verified_against", [])
            notes["hard_distinctness"] = (
                f"medium was not accepted, so hard was checked for distinctness against {' and '.join(compared)} only"
                if compared else "medium was not accepted; no accepted hard numeric distinctness comparison was recorded")
        served_attempts = returned_backend_labels(result, args.backend)
        served_by = served_attempts[-1] if served_attempts else None
        run_log = {"input_file": str(args.file), "backend": args.backend, "endpoint": args.endpoint, "model": args.model,
                   "status": status,
                   "reasoning_effort": args.reasoning_effort,
                   "difficulty": difficulty, "config": vars(config),
                   "distinct_from_proposal_ids": {other["difficulty"]: other["id"] for other in distinct_from},
                   "rate_limit_waits_so_far": list(getattr(getattr(client, "primary", client), "rate_limit_waits", [])),
                   "served_by": served_by, "served_by_attempts": served_attempts,
                   "result": result.as_dict()}
        write_current(args.output_dir / f"{difficulty}_run.json", run_log)
        timings[difficulty] = {"reused": False, "elapsed_seconds": result.elapsed_seconds,
                               "attempts": len(result.attempts)}
        if result.proposal is None:
            errors[difficulty] = result.error.message if result.error else "unknown generation failure"
            if result.error and result.error.code in PROVIDER_FAILURE_CODES:
                provider_failure = result.error.code
            write_current(args.output_dir / f"{difficulty}_proposal.json",
                          {"status": "failed", "proposal": None, "error": result.as_dict()["error"]})
            continue
        result.proposal["served_by"] = served_by
        proposals[difficulty] = result.proposal
        write_current(args.output_dir / f"{difficulty}_proposal.json", result.proposal)

    for level, record in levels.items():
        record.update(proposal=str(args.output_dir / f"{level}_proposal.json"),
                      log=str(args.output_dir / f"{level}_run.json"))
    summary = {"concept_id": card.concept_id, "concept_version": card.card_version, "run_id": run_id, "levels": levels,
               "backend": args.backend, "model": args.model,
               "fallback": (client.event if isinstance(client, FallbackClient) and client.event else
                            {"activated": False, "enabled": isinstance(client, FallbackClient)}), "timings": timings, "errors": errors, "notes": notes,
               "review_flags": {level: proposal.get("review_flags", []) for level, proposal in proposals.items()}}
    if len(proposals) == 3:
        prompts = [proposals[level]["prompt"] for level in ("easy", "medium", "hard")]
        if len(set(prompts)) != 3:
            errors["duplicate_prompts"] = "root questions must have distinct prompts"
        else:
            root_set = {"id": "rqs_" + uuid.uuid4().hex[:12], "kind": "draft_root_question_set",
                        "concept_id": card.concept_id, "concept_version": card.card_version,
                        "subject": card.subject, "grade": card.grade, "review_status": "draft",
                        "root_questions": [proposals[level] for level in ("easy", "medium", "hard")]}
            write_current(args.output_dir / "root_question_set.json", root_set)
            summary["root_question_set"] = str(args.output_dir / "root_question_set.json")
    write_current(args.output_dir / "run_summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 1 if len(proposals) != 3 or "duplicate_prompts" in errors else 0


def main() -> int:
    try:
        return _main()
    except OSError as exc:
        print(f"cannot write generator output: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
