"""Generate one draft easy maths question from a concept-card JSON file."""

import argparse
import json
import os
from pathlib import Path

from concept_card_loader import ConceptCardError, load_file
from model_backends import ModelConfigError, add_backend_args, add_fallback_args, make_client, returned_backend_labels, with_fallback
from question_generator import FallbackClient, GenerationConfig, ModelRequestError, OllamaClient, generate_one


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--concept-id", help="select a card when FILE contains several")
    add_backend_args(parser)
    add_fallback_args(parser)
    parser.add_argument("--difficulty", choices=("easy", "medium", "hard"), default="easy")
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--max-output-tokens", type=int, default=512)
    parser.add_argument("--repairs", type=int, choices=(0, 1), default=1)
    parser.add_argument("--output", type=Path, help="write the proposal JSON here")
    parser.add_argument("--log", type=Path, help="write attempts and timing JSON here")
    args = parser.parse_args()
    try:
        cards = load_file(args.file)
        if args.concept_id:
            cards = [card for card in cards if card.concept_id == args.concept_id]
        if len(cards) != 1:
            parser.error(f"expected one concept card, found {len(cards)}; use --concept-id for a collection")
        config = GenerationConfig(
            timeout=args.timeout,
            max_output_tokens=args.max_output_tokens,
            max_repair_requests=args.repairs,
        )
    except (ConceptCardError, ValueError) as exc:
        parser.error(str(exc))

    try:
        client = make_client(args, OllamaClient)
        if args.list_models:
            if args.backend not in ("groq", "openai"):
                parser.error("--list-models applies to the groq or openai backend only")
            print("\n".join(client.list_models()))
            return 0
        client = with_fallback(client, args, OllamaClient)
    except (ModelConfigError, ModelRequestError, TimeoutError) as exc:
        parser.error(str(exc))
    result = generate_one(cards[0], client, config,
                          difficulty=args.difficulty)
    served_attempts = returned_backend_labels(result, args.backend)
    served_by = served_attempts[-1] if served_attempts else None
    if result.proposal is not None:
        result.proposal["served_by"] = served_by
    payload = result.as_dict()
    if args.log:
        args.log.parent.mkdir(parents=True, exist_ok=True)
        args.log.write_text(
            json.dumps({"input_file": str(args.file), "backend": args.backend, "endpoint": args.endpoint, "model": args.model,
                        "config": vars(config), "served_by": served_by, "served_by_attempts": served_attempts,
                        "fallback": (client.event if isinstance(client, FallbackClient) and client.event else
                                     {"activated": False, "enabled": isinstance(client, FallbackClient)}),
                        "result": payload}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if result.proposal is not None:
        proposal_json = json.dumps(result.proposal, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(proposal_json, encoding="utf-8")
        print(proposal_json, end="")
        print(f"Elapsed: {result.elapsed_seconds:.3f}s; attempts: {len(result.attempts)}")
        return 0
    failure_json = json.dumps({"proposal": None, "error": payload["error"], "attempts": payload["attempts"],
                               "elapsed_seconds": payload["elapsed_seconds"]}, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(failure_json, encoding="utf-8")
    print(failure_json, end="")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
