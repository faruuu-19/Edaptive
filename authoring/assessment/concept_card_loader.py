"""Load concept-card teaching inputs without depending on existing questions.

The source JSON is read only. A file may hold one card, a list of cards, or a
``cards`` collection. Assessment documents and schemas are separate inputs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConceptCardError(ValueError):
    """An input file or concept card cannot be normalized."""


@dataclass(frozen=True)
class TeachingItem:
    id: str | None
    title: str | None
    text: str
    source_ref: dict[str, Any] | None
    asset_ids: tuple[str, ...]
    origin: str | None


@dataclass(frozen=True)
class NormalizedConceptCard:
    concept_id: str
    card_version: int | str
    schema_version: str | None
    subject: str
    grade: int
    prerequisite_ids: tuple[str, ...]
    objective: TeachingItem
    explanations: tuple[TeachingItem, ...]
    examples: tuple[TeachingItem, ...]
    source_refs: tuple[dict[str, Any], ...]
    required_assets: tuple[dict[str, Any], ...]
    review_status: str | None
    review_flags: tuple[dict[str, Any], ...]
    limitations: tuple[str, ...]
    reference_questions: tuple[dict[str, Any], ...]
    reference_rubrics: tuple[dict[str, Any], ...]
    reference_hints: tuple[dict[str, Any], ...]
    input_file: str
    input_location: str
    misconceptions: tuple[dict[str, Any], ...] = ()


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _objects(value: Any, field: str, location: str) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ConceptCardError(f"{location}: {field} must be an array of objects")
    return tuple(value)


def _teaching_item(value: Any, field: str, location: str) -> TeachingItem | None:
    if isinstance(value, str):
        return TeachingItem(None, None, value.strip(), None, (), None) if value.strip() else None
    if not isinstance(value, dict):
        raise ConceptCardError(f"{location}: {field} must be text or an object with text")
    text = value.get("text")
    if text is None or (isinstance(text, str) and not text.strip()):
        return None
    if not isinstance(text, str):
        raise ConceptCardError(f"{location}: {field}.text must be text")
    asset_ids = value.get("asset_ids") or []
    if not isinstance(asset_ids, list) or any(not _nonempty_string(asset_id) for asset_id in asset_ids):
        raise ConceptCardError(f"{location}: {field}.asset_ids must be an array of IDs")
    source_ref = value.get("source_ref")
    if source_ref is not None and not isinstance(source_ref, dict):
        raise ConceptCardError(f"{location}: {field}.source_ref must be an object")
    return TeachingItem(
        id=value.get("id"),
        title=value.get("title"),
        text=text.strip(),
        source_ref=source_ref,
        asset_ids=tuple(asset_ids),
        origin=value.get("origin"),
    )


def _teaching_items(value: Any, field: str, location: str) -> tuple[TeachingItem, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ConceptCardError(f"{location}: {field} must be an array")
    items = []
    for index, raw in enumerate(value):
        item = _teaching_item(raw, f"{field}[{index}]", location)
        if item is not None:
            items.append(item)
    return tuple(items)


def normalize_card(card: dict[str, Any], *, input_file: str, location: str = "$") -> NormalizedConceptCard:
    """Validate the minimum teaching input and retain reference and review data."""
    if not isinstance(card, dict):
        raise ConceptCardError(f"{location}: concept card must be an object")
    for field in ("concept_id", "subject"):
        if not _nonempty_string(card.get(field)):
            raise ConceptCardError(f"{location}: missing or empty {field}")
    version = card.get("card_version")
    if isinstance(version, bool) or not (isinstance(version, int) and version > 0 or _nonempty_string(version)):
        raise ConceptCardError(f"{location}: missing or invalid card_version")
    grade = card.get("grade")
    if isinstance(grade, bool) or not isinstance(grade, int) or grade < 1:
        raise ConceptCardError(f"{location}: missing or invalid grade")
    if "objective" not in card:
        raise ConceptCardError(f"{location}: missing objective")
    objective = _teaching_item(card["objective"], "objective", location)
    if objective is None:
        raise ConceptCardError(f"{location}: missing or empty objective.text")
    explanations = _teaching_items(card.get("explanations"), "explanations", location)
    examples = _teaching_items(card.get("examples"), "examples", location)
    if not explanations and not examples:
        raise ConceptCardError(f"{location}: insufficient teaching content: add a nonempty explanation or example")

    sources = _objects(card.get("source_refs"), "source_refs", location)
    assets = _objects(card.get("assets_required"), "assets_required", location)
    flags = _objects(card.get("review_flags"), "review_flags", location)
    questions = _objects(card.get("questions"), "questions", location)
    rubrics = _objects(card.get("rubrics"), "rubrics", location)
    hints = _objects(card.get("hints"), "hints", location)
    misconceptions = _objects(card.get("misconceptions"), "misconceptions", location)
    prerequisite_ids = card.get("prerequisite_ids") or []
    if not isinstance(prerequisite_ids, list) or any(not _nonempty_string(value) for value in prerequisite_ids):
        raise ConceptCardError(f"{location}: prerequisite_ids must be an array of IDs")
    status = card.get("review_status")
    if status is not None and not _nonempty_string(status):
        raise ConceptCardError(f"{location}: review_status must be text")
    limitations = []
    if status != "approved":
        limitations.append(f"review_status: {status or 'unspecified'}")
    return NormalizedConceptCard(
        concept_id=card["concept_id"].strip(),
        card_version=version,
        schema_version=card.get("schema_version"),
        subject=card["subject"].strip(),
        grade=grade,
        prerequisite_ids=tuple(prerequisite_ids),
        objective=objective,
        explanations=explanations,
        examples=examples,
        source_refs=sources,
        required_assets=assets,
        review_status=status,
        review_flags=flags,
        limitations=tuple(limitations),
        reference_questions=questions,
        reference_rubrics=rubrics,
        reference_hints=hints,
        input_file=input_file,
        input_location=location,
        misconceptions=misconceptions,
    )


def document_kind(document: Any) -> str:
    """Distinguish concept inputs from the schema and existing assessments."""
    if isinstance(document, dict):
        if "$schema" in document:
            return "schema"
        if "assessment_id" in document:
            return "assessment"
    return "concept_cards"


def read_document(path: str | Path) -> Any:
    """One filename-bearing UTF-8/JSON boundary for direct loads and folder scans."""
    path = Path(path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise ConceptCardError(f"{path}: invalid UTF-8 encoding at byte {exc.start}; concept-card files must use UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise ConceptCardError(f"{path}: malformed JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    except OSError as exc:
        raise ConceptCardError(f"{path}: cannot read file: {exc.strerror or exc}") from exc
    return document


def load_file(path: str | Path) -> list[NormalizedConceptCard]:
    path = Path(path)
    document = read_document(path)
    kind = document_kind(document)
    if kind != "concept_cards":
        raise ConceptCardError(f"{path}: {kind} document is not a concept card")
    if isinstance(document, list):
        cards, prefix = document, "$"
    elif isinstance(document, dict) and "cards" in document:
        cards, prefix = document["cards"], "$.cards"
    elif isinstance(document, dict):
        cards, prefix = [document], "$"
    else:
        raise ConceptCardError(f"{path}: expected a concept card, array, or cards collection")
    if not isinstance(cards, list) or not cards:
        raise ConceptCardError(f"{path}: cards must be a nonempty array")
    return [normalize_card(card, input_file=str(path), location=f"{prefix}[{index}]" if prefix != "$" or len(cards) > 1 else "$") for index, card in enumerate(cards)]
