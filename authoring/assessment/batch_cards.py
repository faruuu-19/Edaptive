"""Finding concept cards, choosing which to build, and where each assessment card is written.

Output mirrors how the concept cards are organised: one folder per module (``grade4/Grade 4 Module 3``), holding
``<concept_id>.assessment_card.json``, ``<concept_id>.assessment_card.audit.json`` and one index file for the module that lists
its assessment cards in the same order, with the same ids, as the concept module file. Concept cards are only ever read.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from concept_card_loader import ConceptCardError, NormalizedConceptCard, load_file

CURRICULUM_FOLDER = "Maths Concept Cards Curriculum"
_ID = re.compile(r"^(?P<subject>[a-z]+)_g(?P<grade>\d+)_m(?P<module>\d+)(?:_l(?P<lesson>\d+))?")


@dataclass(frozen=True)
class CardRef:
    concept_id: str
    subject: str | None
    grade: int | None
    module: int | None
    lesson: int | None
    module_key: str
    folder: str                 # relative output folder, e.g. "grade4/Grade 4 Module 3"
    source_file: str            # relative to the project root
    source_path: str            # absolute
    position: int               # index inside the concept file
    card: NormalizedConceptCard


def _ref(card: NormalizedConceptCard, path: Path, root: Path, position: int) -> CardRef:
    found = _ID.match(card.concept_id)
    if found:
        subject, grade, module = found.group("subject"), int(found.group("grade")), int(found.group("module"))
        lesson = int(found.group("lesson")) if found.group("lesson") else None
        key = f"{subject}_g{grade}_m{module}"
        folder = f"grade{grade}/Grade {grade} Module {module}"
    else:
        subject = grade = module = lesson = None
        key = re.sub(r"[^A-Za-z0-9_-]+", "_", path.stem)
        folder = f"other/{key}"
    try:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        relative = path.as_posix()
    return CardRef(card.concept_id, subject, grade, module, lesson, key, folder, relative, str(path), position, card)


def discover(root: Path | str, *, with_problems: bool = False) -> Any:
    """Every concept card under the curriculum folder, in module order. (The loose test card at the project root is not a lesson.)

    Files that are not concept cards (the schema, end-of-module assessments) are skipped. A file that cannot be read is
    reported, never fatal. A concept id seen twice is kept once (the first, in curriculum order).
    """
    root = Path(root)
    files = sorted(p for p in (root / CURRICULUM_FOLDER).rglob("*.json") if p.is_file())
    refs: list[CardRef] = []
    problems: list[str] = []
    seen: set[str] = set()
    for path in files:
        try:
            cards = load_file(path)
        except ConceptCardError as exc:
            text = str(exc)
            if "is not a concept card" not in text:
                problems.append(f"{path.name}: {text}")
            continue
        for index, card in enumerate(cards):
            if card.concept_id in seen:
                continue
            seen.add(card.concept_id)
            refs.append(_ref(card, path, root, index))
    refs.sort(key=lambda r: (r.grade is None, r.grade or 0, r.module or 0, r.source_file, r.position))
    return (refs, problems) if with_problems else refs


def parse_lessons(spec: str) -> set[int]:
    """'28', '11-20' or '1-3,7' -> a set of lesson numbers."""
    lessons: set[int] = set()
    if not isinstance(spec, str) or not spec.strip():
        raise ValueError("a lesson filter needs a number or range such as 28 or 11-20")
    for part in spec.split(","):
        part = part.strip()
        found = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not found:
            raise ValueError(f"cannot read lesson filter {part!r}; use 28, 11-20 or 1-3,7")
        low = int(found.group(1))
        high = int(found.group(2) or low)
        if high < low:
            raise ValueError(f"lesson range {part!r} runs backwards")
        lessons.update(range(low, high + 1))
    return lessons


def select(refs: list[CardRef], *, subject: str | None = None, grade: int | None = None, module: int | None = None,
           lesson: str | int | None = None) -> list[CardRef]:
    wanted = parse_lessons(str(lesson)) if lesson is not None else None
    return [r for r in refs if (subject is None or r.subject == subject) and (grade is None or r.grade == grade)
            and (module is None or r.module == module) and (wanted is None or r.lesson in wanted)]


def card_paths(out_root: Path | str, ref: CardRef) -> tuple[Path, Path]:
    folder = Path(out_root) / ref.folder
    return folder / f"{ref.concept_id}.assessment_card.json", folder / f"{ref.concept_id}.assessment_card.audit.json"


def index_path(out_root: Path | str, module_key: str, folder: str = "") -> Path:
    return Path(out_root) / folder / f"{module_key}.assessment_cards.json"


def check_output_root(out_root: Path | str, root: Path | str) -> None:
    """Concept cards must never be written to: the output folder may not be inside the curriculum folder."""
    out, curriculum = Path(out_root).resolve(), (Path(root) / CURRICULUM_FOLDER).resolve()
    if out == curriculum or curriculum in out.parents:
        raise ValueError(f"the output folder {out} is inside the concept-card folder; concept cards are never edited")


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{uuid.uuid4().hex[:8]}.tmp")
    try:
        with temp.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def write_card_files(out_root: Path | str, ref: CardRef, card: dict[str, Any], audit: dict[str, Any]) -> tuple[Path, Path]:
    """The audit is written first: a card file never exists without its audit beside it."""
    card_path, audit_path = card_paths(out_root, ref)
    atomic_write(audit_path, audit)
    atomic_write(card_path, card)
    return card_path, audit_path


def read_card(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) and isinstance(value.get("readiness"), dict) else None


def rebuild_module_index(out_root: Path | str, module_refs: list[CardRef], module_key: str) -> Path:
    """Rewrite the module's index from the card files on disk, in the concept module file's order."""
    ordered = sorted((r for r in module_refs if r.module_key == module_key), key=lambda r: (r.source_file, r.position))
    entries = []
    for ref in ordered:
        card_path, audit_path = card_paths(out_root, ref)
        card = read_card(card_path)
        if card is None or not audit_path.exists():
            continue
        entries.append({"concept_id": ref.concept_id, "assessment_card_id": card.get("assessment_card_id"), "file": card_path.name,
                        "audit_file": audit_path.name, "ready_for_delivery": card["readiness"].get("ready_for_delivery"),
                        "difficulty_levels": card.get("difficulty_levels"), "review_status": card.get("review_status")})
    first = ordered[0] if ordered else None
    index = {"schema_version": "0.1-draft", "collection_id": f"{module_key}_assessment_cards",
             "concept_collection_file": first.source_file if first else None,
             "concept_card_count": len(ordered), "assessment_card_count": len(entries), "cards": entries}
    path = index_path(out_root, module_key, first.folder if first else "")
    atomic_write(path, index)
    return path
