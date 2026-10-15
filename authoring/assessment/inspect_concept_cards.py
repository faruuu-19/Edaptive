"""Print concise concept-card summaries and scan the curriculum folder."""

import argparse
import json
from pathlib import Path

from concept_card_loader import ConceptCardError, document_kind, load_file, read_document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", type=Path, help="JSON concept-card file to summarize")
    parser.add_argument("--scan", type=Path, metavar="FOLDER", help="scan all concept-card JSON files under FOLDER")
    args = parser.parse_args()
    if not args.file and not args.scan:
        parser.error("provide a file or --scan FOLDER")
    failures = []
    if args.file:
        try:
            for card in load_file(args.file):
                print(f"{card.concept_id} v{card.card_version} | {card.subject} grade {card.grade}")
                print(f"  objective: {card.objective.text}")
                print(f"  teaching: {len(card.explanations)} explanations, {len(card.examples)} examples; "
                      f"optional references: {len(card.reference_questions)} questions, "
                      f"{len(card.reference_rubrics)} rubrics, {len(card.reference_hints)} hints")
                print(f"  sources: {len(card.source_refs)}; required assets: {len(card.required_assets)}; "
                      f"review flags: {len(card.review_flags)}")
                for limitation in card.limitations:
                    print(f"  limitation: {limitation}")
        except ConceptCardError as exc:
            failures.append(str(exc))
    if args.scan:
        loaded = 0
        scanned = 0
        skipped = []
        for path in sorted(args.scan.rglob("*.json")):
            scanned += 1
            try:
                document = read_document(path)
                kind = document_kind(document)
                if kind != "concept_cards":
                    skipped.append(f"{path}: {kind}")
                    continue
                loaded += len(load_file(path))
            except (ConceptCardError, json.JSONDecodeError, OSError) as exc:
                failures.append(f"{path}: {exc}")
        print(f"Scan: {loaded} concept cards loaded from {scanned} JSON files; "
              f"{len(skipped)} non-card files; {len(failures)} failures")
        for item in skipped:
            print(f"  skipped: {item}")
    for failure in failures:
        print(f"  FAILED: {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
