"""What a lesson teaches, read from the concept card itself (never from its id): operations, rules, number domain, kind.

Three kinds of lesson:
  calculation      it teaches add / subtract / multiply / divide (whole numbers, fractions, decimals or money);
                   every answer is computed by code (calculator.py).
  rule_checkable   it teaches comparison, rounding or place value; every answer is computed by code.
  non_calculation  naming, shapes, English, Science ... or a lesson with nothing code can check. Questions are grounded in
                   the card's own text and are never described as code-verified.

Everything here works from wording cues, so it is a heuristic. A cue only counts as *taught* when the objective names it or
at least two explanations/examples use it: one passing mention does not make something taught.
"""

from __future__ import annotations

import re
from typing import Any

from concept_card_loader import NormalizedConceptCard

MIN_ITEMS_FOR_TAUGHT = 2
MIN_CHECKABLE_ANSWER_SHARE = 0.4

OPERATION_CUES = {
    "add": r"\b(?:plus|add|adds|added|adding|addition|sum)\b|\+",
    "subtract": r"\b(?:minus|subtract\w*|take|takes|taking|difference)\b|−",
    "multiply": r"\b(?:times|multipl\w*|product)\b|×",
    "divide": r"\b(?:divid\w*|division|quotient|share[sd]? equally)\b|÷",
}
INVERSE_OPERATION = {"add": "subtract", "subtract": "add", "multiply": "divide", "divide": "multiply"}
RULE_CUES = {
    "compare": r"\b(?:compar\w*\s+(?:\w+\s+){0,2}?(?:numbers?|fractions?|decimals?|amounts?|values?)|greater than|less than|"
               r"order(?:ing)? numbers|symbols? (?:<|>|for))\b|[<>]",
    "round": r"\b(?:round\w*|nearest (?:ten|hundred|thousand|one|whole number))\b",
    "place_value": r"\b(?:place value|expanded form|standard form|word form|unit form|value of the digit|digit in the)\b",
}
DOMAIN_CUES = {
    "money": r"\b(?:dollars?|cents?|coins?|money|prices?|priced|costs?)\b|\$",
    "decimal": r"\b(?:decimals?|tenths|hundredths|thousandths)\b",
    "fraction": r"\b(?:fractions?|numerators?|denominators?|mixed numbers?|halves|thirds|fourths|fifths|sixths|eighths)\b|\b\d+/\d+\b",
}
_REPEATED_ADDITION = r"\brepeated addition\b"
_SYMBOLS = ("<", ">", "=", "less than", "greater than", "equal to", "more than", "equals")
_CHECKABLE_ANSWER = re.compile(
    r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:\s+[A-Za-z][A-Za-z ]*)?"   # 37,000 / 7 ones / 0.75 / 12 cents
    r"|\$\s?\d[\d,]*(?:\.\d+)?"                                            # $12.50
    r"|-?\d+\s+\d+/\d+|-?\d+/\d+|\d+\s+and\s+\d+/\d+"                        # 3/4, 1 3/4 and 1 and 2/8
    r"|\d+\s*(?:r|R|rem|remainder)\s*\d+")                                       # 7 R 5 (quotient and remainder)
_MATH_SUBJECTS = ("math", "maths", "mathematics")


def _items(card: NormalizedConceptCard) -> list[str]:
    return [item.text.lower() for item in (*card.explanations, *card.examples)]


def _taught(card: NormalizedConceptCard, cues: dict[str, str]) -> list[str]:
    objective = card.objective.text.lower()
    items = _items(card)
    return [name for name, pattern in cues.items()
            if re.search(pattern, objective) or sum(1 for text in items if re.search(pattern, text)) >= MIN_ITEMS_FOR_TAUGHT]


def taught_operations(card: NormalizedConceptCard) -> list[str]:
    """What the lesson teaches. The objective decides: if it names operations, those are taught (an operation that only two
    items happen to mention is a method used along the way, not the goal). If the objective names none, an operation used by at
    least two explanations or examples is taught."""
    objective = card.objective.text.lower()
    named = [name for name, pattern in OPERATION_CUES.items() if re.search(pattern, objective)]
    return named or _taught(card, OPERATION_CUES)


def mentioned_operations(card: NormalizedConceptCard) -> list[str]:
    """Operations named anywhere in the teaching, even once. Never used to decide what is taught."""
    text = " ".join([card.objective.text, *_items(card)]).lower()
    return [name for name, pattern in OPERATION_CUES.items() if re.search(pattern, text)]


def permitted_operations(card: NormalizedConceptCard) -> list[str]:
    """Taught operations plus the inverse of a taught one when the card also mentions it (an inverse cross-check needs it)."""
    taught = taught_operations(card)
    mentioned = mentioned_operations(card)
    return taught + [INVERSE_OPERATION[name] for name in taught
                     if INVERSE_OPERATION[name] not in taught and INVERSE_OPERATION[name] in mentioned]


def taught_rules(card: NormalizedConceptCard) -> list[str]:
    return _taught(card, RULE_CUES)


def teaches_repeated_addition(card: NormalizedConceptCard) -> bool:
    objective = card.objective.text.lower()
    return bool(re.search(_REPEATED_ADDITION, objective)
                or sum(1 for text in _items(card) if re.search(_REPEATED_ADDITION, text)) >= MIN_ITEMS_FOR_TAUGHT)


def _answer_shape(text: Any) -> str | None:
    text = str(text).strip()
    if re.fullmatch(r"\$\s?\d[\d,]*(?:\.\d+)?|\d+(?:\.\d+)?\s+(?:dollars?|cents?)(?:\b.*)?", text, re.I):
        return "money"
    if re.fullmatch(r"-?\d+\s+\d+/\d+|-?\d+/\d+|\d+\s+and\s+\d+/\d+", text):
        return "fraction"
    if re.fullmatch(r"-?\d*\.\d+(?:\s+[A-Za-z][A-Za-z ]*)?", text):
        return "decimal"
    if re.fullmatch(r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\s+[A-Za-z][A-Za-z ]*)?|\d+\s*(?:r|R|rem|remainder)\s*\d+", text):
        return "integer"
    return None


MIN_TYPED_ANSWER_SHARE = 0.3


def objective_domain(card: NormalizedConceptCard) -> str | None:
    """The number domain the objective itself names (fractions, decimals, money), if any."""
    objective = card.objective.text.lower()
    for name in ("money", "decimal", "fraction"):
        if re.search(DOMAIN_CUES[name], objective):
            return name
    return None


def lesson_domain(card: NormalizedConceptCard) -> str:
    """integer, fraction, decimal or money: which kind of number the lesson works with.

    What the objective names comes first. Otherwise the shape of the card's own accepted answers decides (what the lesson
    actually asks children to produce); wording cues in the teaching items are the last fallback.
    """
    named = objective_domain(card)
    if named:
        return named
    rubrics = {rubric.get("id"): rubric for rubric in card.reference_rubrics}
    shapes = []
    for question in card.reference_questions:
        key = (rubrics.get(question.get("rubric_id")) or {}).get("answer_key") or {}
        accepted = key.get("accept") or []
        if key.get("mode") == "exact" and accepted and _answer_shape(accepted[0]):
            shapes.append(_answer_shape(accepted[0]))
    if shapes:
        for name in ("money", "decimal", "fraction"):
            if shapes.count(name) / len(shapes) >= MIN_TYPED_ANSWER_SHARE:
                return name
        return "integer"
    found = _taught(card, DOMAIN_CUES)
    for name in ("money", "decimal", "fraction"):
        if name in found:
            return name
    return "integer"


def answer_is_checkable(text: Any) -> bool:
    """Could code check an answer of this shape: a number, fraction, decimal, money amount or a comparison symbol?"""
    text = str(text).strip()
    return bool(_CHECKABLE_ANSWER.fullmatch(text)) or text.lower() in _SYMBOLS


def checkable_answer_share(card: NormalizedConceptCard) -> float | None:
    """Share of the card's own questions whose exact rubric accepts an answer code could check. None without questions."""
    if not card.reference_questions:
        return None
    rubrics = {rubric.get("id"): rubric for rubric in card.reference_rubrics}
    checkable = 0
    for question in card.reference_questions:
        key = (rubrics.get(question.get("rubric_id")) or {}).get("answer_key") or {}
        accepted = key.get("accept") or []
        if key.get("mode") == "exact" and accepted and answer_is_checkable(accepted[0]):
            checkable += 1
    return checkable / len(card.reference_questions)


def rules_named_in_objective(card: NormalizedConceptCard) -> list[str]:
    objective = card.objective.text.lower()
    return [rule for rule in taught_rules(card) if re.search(RULE_CUES[rule], objective)]


def lesson_kind(card: NormalizedConceptCard) -> str:
    if str(card.subject).lower() not in _MATH_SUBJECTS:
        return "non_calculation"
    share = checkable_answer_share(card)
    nothing_checkable = share is not None and share < MIN_CHECKABLE_ANSWER_SHARE
    # A lesson whose own answers are words (shapes, naming) has nothing code can check, unless its objective itself names a
    # number domain or a rule: those are checkable by nature whatever the stored answers look like.
    if taught_operations(card) and (not nothing_checkable or objective_domain(card)):
        return "calculation"
    if taught_rules(card) and (not nothing_checkable or rules_named_in_objective(card)):
        return "rule_checkable"
    return "non_calculation"
