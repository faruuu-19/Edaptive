"""Build an assessment card from a concept card: reuse its own questions first, generate only what is missing."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import assessment_card as ac
from concept_card_loader import ConceptCardError, NormalizedConceptCard, load_file
from model_backends import ModelConfigError, PacedClient, add_backend_args, add_fallback_args, make_client, returned_backend_labels, with_fallback
from question_generator import PROVIDER_FAILURE_CODES, GenerationConfig, GenerationError, GenerationResult, ModelRequestError, OllamaClient, generate_one, validate_saved_proposal

# These stop the rest of a build: the client already waited its bounded retries on a 429, a bad key or an unreachable provider
# will fail the next request too. request_rejected (a 400, an over-long reply) is deliberately NOT here: it fails only that level.
_PROVIDER_FAILURES = PROVIDER_FAILURE_CODES
_OUTPUT_NAMES = ("assessment_card.json", "assessment_card.audit.json", "assembly_run.json")


@dataclass
class BuildResult:
    card: dict[str, Any] | None
    audit: dict[str, Any]
    run: dict[str, Any]
    exit_code: int


def _generation_record(result: GenerationResult, backend: str) -> dict[str, Any]:
    return {"elapsed_seconds": result.elapsed_seconds, "attempts": len(result.attempts),
            "served_by": (returned_backend_labels(result, backend) or [None])[-1], "result": result.as_dict()}


def _generate(card: NormalizedConceptCard, client: Any, config: GenerationConfig, **kwargs: Any) -> GenerationResult:
    """generate_one, but an unexpected exception (a bug, not a model problem) becomes a recorded ``internal_error`` for that level.

    One bad lesson, or one bad level, must never stop an unattended run. Ctrl-C is not an Exception and still stops it.
    """
    try:
        return generate_one(card, client, config, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return GenerationResult(None, GenerationError("internal_error", f"{type(exc).__name__}: {exc}"), (), 0.0)


def build(card: NormalizedConceptCard, config: GenerationConfig, *, client: Any = None,
          saved_proposals: dict[str, Any] | None = None, backend: str = "groq", follow_ups: bool = True,
          allow_asset_blocked: bool = True, card_version: int = 1, run_id: str | None = None,
          proposal_cache: Any = None) -> BuildResult:
    """Choose reuse per level, fill the gaps from a saved root question set or the model, then assemble.

    A provider failure (daily quota with no fallback, a bad key) stops every later model request in the build,
    scaffolds included, and is named in ``run["provider_failure"]``. A validation failure does not: each level stands on its own.

    ``proposal_cache`` (optional, anything with get(key) / put(key, proposal)) keeps each accepted model answer the moment it
    arrives, under ``level:<level>`` and ``followup:<level>``, and hands it back on a rerun after the current rules recheck it,
    so a card that was stopped part way never repeats a call that already succeeded.
    """
    run_id = run_id or "run_" + uuid.uuid4().hex
    saved = {q["difficulty"]: q for q in (saved_proposals or {}).get("root_questions", []) if isinstance(q, dict)}
    plan = ac.plan_reuse(card, allow_asset_blocked=allow_asset_blocked)
    run: dict[str, Any] = {"run_id": run_id, "backend": backend, "levels": {}, "follow_ups": {}, "errors": {}, "generation": {}}
    choices: dict[str, dict[str, Any]] = {}
    generated: dict[str, dict[str, Any]] = {}
    provider_failure: str | None = None
    missing_reasons: dict[str, str] = {}

    def skipped_note(what: str) -> str:
        return f"{what} not attempted: the provider failed earlier in this run ({provider_failure})"

    for level in ac.LEVELS:
        record: dict[str, Any] = {"reuse_rule": plan[level]["rule"], "reuse_alternatives": plan[level]["eligible_in_rank_order"],
                                  "reuse_rejected": plan[level]["rejected"],
                                  "unused_saved_proposal": (saved.get(level) or {}).get("id")}
        run["levels"][level] = record
        picked = plan[level]["choice"]
        if picked is not None:
            choices[level] = {"origin": "reused", "candidate": picked}
            record.update(status="reused", concept_card_question=picked["question"]["id"])
            continue
        proposal = None
        if level in saved:
            try:
                proposal = validate_saved_proposal(copy.deepcopy(saved[level]), card, config)
                proposal["run_id"] = saved[level].get("run_id")
                proposal["served_by"] = saved[level].get("served_by")
                record.update(status="saved_proposal", unused_saved_proposal=None, proposal_id=proposal["id"])
            except ValueError as exc:
                run["errors"][f"{level}_saved"] = f"saved {level} proposal rejected by the current rules: {exc}"
        if proposal is None and proposal_cache is not None and proposal_cache.get(f"level:{level}"):
            try:
                proposal = validate_saved_proposal(copy.deepcopy(proposal_cache.get(f"level:{level}")), card, config)
                proposal["run_id"] = proposal_cache.get(f"level:{level}").get("run_id")
                proposal["served_by"] = proposal_cache.get(f"level:{level}").get("served_by")
                record.update(status="generated", proposal_id=proposal["id"], from_cache=True)
            except (ValueError, KeyError, TypeError) as exc:
                proposal = None
                run["errors"][f"{level}_cached"] = f"cached {level} answer rejected by the current rules: {exc}"
        if proposal is None:
            if provider_failure:
                run["errors"][level] = skipped_note(level)
                missing_reasons[level] = f"not generated: {run['errors'][level]}"
                record.update(status="skipped")
                continue
            if client is None:
                run["errors"][level] = f"{level} needs a model request but no model client was configured"
                missing_reasons[level] = f"not generated: {run['errors'][level]}"
                record.update(status="failed")
                continue
            result = _generate(card, client, config, difficulty=level, distinct_from=list(generated.values()))
            run["generation"][level] = _generation_record(result, backend)
            if result.proposal is None:
                run["errors"][level] = f"{result.error.code}: {result.error.message}"
                if result.error.code == "hard_not_supported":
                    record.update(status="not_supported")
                    missing_reasons[level] = f"not built: {result.error.message}"
                else:
                    record.update(status="failed")
                    missing_reasons[level] = f"generation failed: {result.error.code}: {result.error.message[:240]}"
                if result.error.code in _PROVIDER_FAILURES:
                    provider_failure = result.error.code
                continue
            proposal = result.proposal
            record.update(status="generated", proposal_id=proposal["id"])
            if proposal_cache is not None:
                proposal_cache.put(f"level:{level}", proposal)
        generated[level] = proposal
        choices[level] = {"origin": "generated", "proposal": proposal}

    followups: dict[str, dict[str, Any]] = {}
    if follow_ups:
        for level in ac.FOLLOW_UP_LEVEL:
            if level not in generated:
                continue
            parent_id = f"aq_{ac.LEVEL_CODE[level]}_01"
            cached = proposal_cache.get(f"followup:{level}") if proposal_cache is not None else None
            if cached:
                try:
                    followups[level] = {"proposal": validate_saved_proposal(copy.deepcopy(cached), card, config)}
                    run["follow_ups"][parent_id] = {"from_cache": True}
                    continue
                except (ValueError, KeyError, TypeError) as exc:
                    run["errors"][f"{parent_id}_cached"] = f"cached follow-up rejected by the current rules: {exc}"
            if provider_failure:
                followups[level] = {"error": skipped_note(f"the {level} follow-up")}
                continue
            if client is None:
                followups[level] = {"error": "no model client was configured"}
                continue
            result = _generate(card, client, config, difficulty=ac.FOLLOW_UP_LEVEL[level], distinct_from=[generated[level]],
                               scaffold_of=generated[level])
            run["follow_ups"][parent_id] = _generation_record(result, backend)
            if result.proposal is not None:
                followups[level] = {"proposal": result.proposal}
                if proposal_cache is not None:
                    proposal_cache.put(f"followup:{level}", result.proposal)
            else:
                followups[level] = {"error": f"{result.error.code}: {result.error.message}"}
                if result.error.code in _PROVIDER_FAILURES:
                    provider_failure = result.error.code

    if provider_failure:
        run["provider_failure"] = provider_failure
    source = {"concept_id": card.concept_id, "concept_version": card.card_version, "concept_file": card.input_file,
              "saved_root_question_set": (saved_proposals or {}).get("id"), "run_id": run_id}
    if len(choices) < ac.MIN_LEVELS:
        missing = [level for level in ac.LEVELS if level not in choices]
        run["errors"]["card"] = (f"only {len(choices)} of 3 levels could be chosen or generated (missing: {', '.join(missing)}); "
                                 f"a card needs at least {ac.MIN_LEVELS}, so no card was built")
        audit = {"source": source, "run_id": run_id, "questions": {}, "follow_ups": {}, "notes": [run["errors"]["card"]]}
        return BuildResult(None, audit, run, 1)
    built, audit = ac.assemble_card(card, choices, followups, card_version=card_version, source=source,
                                    missing_reasons=missing_reasons)
    audit["run_id"] = run_id
    return BuildResult(built, audit, run, 0)


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _archive_outputs(directory: Path) -> None:
    import shutil
    existing = [directory / name for name in _OUTPUT_NAMES if (directory / name).exists()]
    if not existing:
        return
    archive = directory / "previous-runs" / ("previous-run-" + uuid.uuid4().hex)
    archive.mkdir(parents=True)
    for path in existing:
        if not path.is_file():
            raise OSError(f"known output is not a file: {path}")
        shutil.move(str(path), str(archive / path.name))


def _load_saved_set(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("root_questions"), list):
        raise ValueError(f"{path} is not a root question set (no root_questions list)")
    return data


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--concept-id", help="select a card from a collection")
    parser.add_argument("--root-set", type=Path, help="a verified root_question_set.json to take generated levels from instead of asking the model")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/assessment-card"))
    parser.add_argument("--card-version", type=int, default=1)
    parser.add_argument("--no-follow-ups", action="store_true", help="do not generate scaffolded follow-ups")
    parser.add_argument("--no-reuse-undescribed-asset", "--no-reuse-asset-blocked", dest="no_reuse_asset_blocked", action="store_true",
                        help="do not reuse a concept-card question whose asset has no usable text description (an asset that is merely "
                             "not drawn yet is fine); generate those levels instead. The older name --no-reuse-asset-blocked still works")
    add_backend_args(parser)
    add_fallback_args(parser)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--max-output-tokens", type=int, default=1024)
    parser.add_argument("--repairs", type=int, choices=(0, 1), default=1)
    parser.add_argument("--min-seconds-between-requests", type=float, default=0.0,
                        help="wait so successive model requests are at least this far apart (keeps a build under a tokens-per-minute "
                             "cap; a 429 still stops the build exactly as before)")
    args = parser.parse_args()
    try:
        cards = load_file(args.file)
        if args.concept_id:
            cards = [c for c in cards if c.concept_id == args.concept_id]
        if len(cards) != 1:
            parser.error(f"expected one concept card, found {len(cards)}; use --concept-id")
        card = cards[0]
        config = GenerationConfig(timeout=args.timeout, max_output_tokens=args.max_output_tokens, max_repair_requests=args.repairs)
        saved_set = _load_saved_set(args.root_set)
    except (ConceptCardError, ValueError, OSError) as exc:
        parser.error(str(exc))

    plan = ac.plan_reuse(card, allow_asset_blocked=not args.no_reuse_asset_blocked)
    gaps = [level for level in ac.LEVELS if plan[level]["choice"] is None]
    saved_levels = {q.get("difficulty") for q in (saved_set or {}).get("root_questions", []) if isinstance(q, dict)}
    needs_model = any(level not in saved_levels for level in gaps) or (not args.no_follow_ups and any(l in gaps for l in ac.FOLLOW_UP_LEVEL))
    client = None
    if needs_model:
        try:
            client = with_fallback(make_client(args, OllamaClient), args, OllamaClient)  # a missing key fails before any file is written
            if args.min_seconds_between_requests > 0:
                client = PacedClient(client, args.min_seconds_between_requests)
        except (ModelConfigError, ModelRequestError, TimeoutError) as exc:
            parser.error(str(exc))
    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        _archive_outputs(args.output_dir)
    except OSError as exc:
        print(f"cannot write assessment card output: {exc}", file=sys.stderr)
        return 1
    started = time.perf_counter()
    result = build(card, config, client=client, saved_proposals=saved_set, backend=args.backend, follow_ups=not args.no_follow_ups,
                   allow_asset_blocked=not args.no_reuse_asset_blocked, card_version=args.card_version)
    result.run["elapsed_seconds"] = time.perf_counter() - started
    result.run["rate_limit_observations"] = list(getattr(client, "observations", []) or [])
    try:
        if result.card is not None:
            _write(args.output_dir / "assessment_card.json", result.card)
        _write(args.output_dir / "assessment_card.audit.json", result.audit)
        _write(args.output_dir / "assembly_run.json", result.run)
    except OSError as exc:
        print(f"cannot write assessment card output: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"assessment_card": str(args.output_dir / "assessment_card.json") if result.card else None,
                      "run_id": result.run["run_id"], "levels": {k: v["status"] for k, v in result.run["levels"].items()},
                      "errors": result.run["errors"], "notes": result.audit["notes"]}, indent=2, ensure_ascii=False))
    return result.exit_code


def main() -> int:
    try:
        return _main()
    except OSError as exc:
        print(f"cannot write assessment card output: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
