"""Assemble an assessment card in the target structure from a concept card and verified generator output.

Nothing here calls a model. It chooses what to reuse from the concept card, maps verified generator proposals into the
target shape, and computes readiness from data the concept card and generator already expose.

PROPOSED RULES (implementation choices for review, not already-approved specification):
  * The concept card's questions carry no difficulty, so reuse is decided by question KIND: ``practice`` items may
    be the easy question, ``application`` items the hard question, and no kind marks a medium question (so medium
    is always generated). This mirrors the target example, which reuses a practice item for easy and an
    application item for hard.
  * A reusable item must have an exact-answer rubric. An easy item must come from a section that also holds a
    taught explanation or example (so a timed-sprint drill is not easy "material").
  * Among eligible items the best fit to the level wins (calculations before definitions), then the one that blocks
    readiness least, then card order. A hard item that is one step or not self-contained is rejected (arithmetic lessons only).
  * A generated medium or hard question gets one scaffolded follow-up, one level easier.

REVISED RULES (stated by the user):
  * A card needs at least 2 of the 3 levels, in any combination.
  * An assessment card never contains an image and never depends on one existing. Whether an asset is drawn
    (its ``status``) is never read here. A stimulus carries a reference plus the asset's text description, and rendering
    happens downstream. The only asset condition left is about TEXT: a reused question whose asset has no usable
    description (description, must_show_exactly, states_or_frames, alt_text) or is not listed in assets_required cannot be
    drawn later, so it blocks (CLAUDE.md section 5).
"""

from __future__ import annotations

import copy
import re
from typing import Any

import calculator
import lesson_profile as lp
from concept_card_loader import NormalizedConceptCard, TeachingItem

SCHEMA_VERSION = "0.1-draft"
CARD_TYPE = "assessment_card"
GENERATED_BY = "assessment_card_generator"
REUSE_POLICY = "prefer_existing_questions_then_generate_missing"
LEVELS = ("easy", "medium", "hard")
LEVEL_CODE = {"easy": "easy", "medium": "med", "hard": "hard"}
MAX_ATTEMPTS_DEFAULT = 2
MIN_LEVELS = 2  # a card needs at least 2 of the 3 difficulty levels, in any combination
# What a concept-card asset must say for a downstream agent to draw it: what it is, what it must show exactly, how it
# changes, and its alt text (the shape of the concept card's own assets_required).
ASSET_DESCRIPTION_FIELDS = ("description", "must_show_exactly", "states_or_frames", "alt_text")
DEFAULT_OUTCOME_ROUTES = {
    "correct": "advance_to_next_question_or_close",
    "partial": "use_only_if_partial_credit_eligible_else_same_as_incorrect",
    "incorrect": "give_next_hint_then_retry_until_max_attempts",
    "unclear": "reprompt_once_then_treat_as_incorrect",
}
FALLBACK_RULES = {
    "on_help_requested": "give_next_hint_level_without_using_an_attempt",
    "on_silence_seconds": 20,
    "on_silence_action": "treat_as_unclear",
    "on_repeated_failure": "after_max_attempts_reveal_answer_reference_and_advance",
    # The reference example also had on_required_asset_unavailable. It is dropped on purpose: a card holds only a
    # description of what to draw, so a picture that does not exist yet never stops a question being delivered.
}
DRAFT_BLOCKER = "card review_status is draft; needs human review before use"
REUSE_KIND = {"easy": "practice", "hard": "application"}
FOLLOW_UP_LEVEL = {"medium": "easy", "hard": "medium"}  # difficulty of the scaffold generated for a question
FOLLOW_UP_PREFIX = "Let's try an easier one: "
INCOMPLETE_PREFIX = "Let's take it one step at a time. "
_NO_KIND_RULE = "no concept-card question kind marks a medium question, so medium is always generated"


class AssemblyError(ValueError):
    """The card cannot be assembled from what was supplied."""


def ref(scope: str, item_id: str) -> dict[str, str]:
    return {"scope": scope, "id": item_id}


# ---------------------------------------------------------------------------------------------------- answer forms
_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
         "seventeen eighteen nineteen").split()
_TENS = (None, None, "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def _below_hundred(n: int, hyphen: bool) -> str:
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens] if not ones else _TENS[tens] + ("-" if hyphen else " ") + _ONES[ones]


def _words(n: int, hyphen: bool, use_and: bool) -> str:
    if n < 100:
        return _below_hundred(n, hyphen)
    joiner = " and " if use_and else " "
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        head = _ONES[hundreds] + " hundred"
        return head if not rest else head + joiner + _below_hundred(rest, hyphen)
    thousands, rest = divmod(n, 1000)
    head = _words(thousands, hyphen, use_and) + " thousand"
    if not rest:
        return head
    return head + (joiner + _below_hundred(rest, hyphen) if rest < 100 else " " + _words(rest, hyphen, use_and))


def number_forms(n: int) -> list[str]:
    """The accepted spellings of a whole-number answer, in the pattern the concept cards' own exact rubrics use.

    Digits first, a comma form from 1,000, then words: space-separated before hyphenated, without 'and' before with
    (``620`` -> ``620``, ``six hundred twenty``, ``six hundred and twenty``). Duplicates are dropped.
    """
    if isinstance(n, bool) or not isinstance(n, int) or not 0 <= n < 100000:
        raise ValueError(f"number_forms supports whole numbers from 0 to 99,999, not {n!r}")
    forms = [str(n)]
    if n >= 1000:
        forms.append(f"{n:,}")
    for use_and in (False, True):
        for hyphen in (False, True):
            forms.append(_words(n, hyphen, use_and))
    return list(dict.fromkeys(forms))


# ----------------------------------------------------------------------------------------- flags that name an item
_ID_TOKEN = re.compile(r"\b[qrh]_[a-z0-9]+(?:_[a-z0-9]+)*\b")
_RANGE = re.compile(r"\b([qrh]_[a-z]+_)(\d+)\s*(?:to|-|–|—)\s*(?:\1)?(\d+)\b")
_MAX_RANGE = 200


def ids_named(text: str) -> set[str]:
    """Question/rubric/hint IDs a free-text flag names, including 'q_pr_7-9' and 'r_pr_5 to r_pr_10' ranges."""
    named = set(_ID_TOKEN.findall(text or ""))
    for prefix, low, high in _RANGE.findall(text or ""):
        low, high = int(low), int(high)
        if low <= high and high - low < _MAX_RANGE:
            named.update(f"{prefix}{number}" for number in range(low, high + 1))
    return named


def uncertainty_signals(card: NormalizedConceptCard, question: dict[str, Any], rubric: dict[str, Any]) -> list[dict[str, Any]]:
    """Direct reads of the concept card: flags that name this question/rubric, and a rubric whose answer is derived.

    A flag counts when it names the item, whatever it is about: the flags are free text and no code here classifies
    their meaning. A derived answer is one the card says was computed, not printed in its source.
    """
    signals = []
    wanted = {question.get("id"), rubric.get("id")}
    named = [flag["id"] for flag in card.review_flags if wanted & ids_named(f"{flag.get('item', '')} {flag.get('issue', '')}")]
    if named:
        signals.append({"kind": "named_in_review_flags", "flag_ids": named})
    if rubric.get("origin") == "derived":
        derived = [flag["id"] for flag in card.review_flags if "derived" in str(flag.get("item", "")).lower()]
        signals.append({"kind": "derived_answer", "flag_ids": derived})
    return signals


# --------------------------------------------------------------------------------------------------------- reuse
def _asset(card: NormalizedConceptCard, asset_id: str) -> dict[str, Any] | None:
    return next((asset for asset in card.required_assets if asset.get("asset_id") == asset_id), None)


def missing_description_fields(asset: dict[str, Any]) -> list[str]:
    """Which of the fields an asset must carry are absent, blank or empty."""
    def usable(value: Any) -> bool:
        if isinstance(value, str):
            return bool(value.strip())
        return isinstance(value, list) and any(isinstance(v, str) and v.strip() for v in value)
    return [field for field in ASSET_DESCRIPTION_FIELDS if not usable(asset.get(field))]


def asset_problems(card: NormalizedConceptCard, asset_ids: list[str]) -> dict[str, str]:
    """asset id -> why a downstream agent could not draw it from the card. Only the text description is judged, never the image."""
    problems = {}
    for asset_id in asset_ids:
        asset = _asset(card, asset_id)
        if asset is None:
            problems[asset_id] = "not listed in assets_required"
            continue
        missing = missing_description_fields(asset)
        if missing:
            problems[asset_id] = ", ".join(missing)
    return problems


def section_family(section: str | None) -> str:
    """The leading phrase of a free-text section name: 'Concept Development, Problem 2 (T: ...)' -> 'concept development'."""
    return re.split(r"[,(:;]", str(section or ""), maxsplit=1)[0].strip().lower()


def _teaching_sections(card: NormalizedConceptCard) -> set[str]:
    return {section_family(item.source_ref["section"]) for item in (*card.explanations, *card.examples)
            if isinstance(item.source_ref, dict) and item.source_ref.get("section")}


# ------------------------------------------------------------------ re-deriving a reused answer by code, where possible
_UNITS = r"(?:ones|tens|hundreds|thousands|ten thousands|hundred thousands)"
_BARE_CALCULATION = re.compile(
    rf"^\s*(?:what is|find|calculate)\s+(\d[\d,]*)(?:\s+({_UNITS}))?\s+(plus|minus|times|divided by)\s+(\d[\d,]*)(?:\s+({_UNITS}))?\s*\??\s*$",
    re.I)
_DIVIDE_QUESTION = re.compile(
    r"^\s*(?:divide\s+(\d[\d,]*)\s+by\s+(\d[\d,]*)|what is\s+(\d[\d,]*)\s+divided by\s+(\d[\d,]*))\s*[.?]?(?:\s+(?-i:[A-Z])[^.?]*[.?])?\s*$", re.I)
_LEADING_NUMBER = re.compile(r"^\s*(-?\d[\d,]*)(?:\s+([A-Za-z][A-Za-z ]*))?\s*$")


def verify_reused_answer(question: dict[str, Any], rubric: dict[str, Any]) -> dict[str, Any] | None:
    """Recompute a reused question's stored answer when the question is a bare calculation ("What is 3,134 plus 2,493?").

    Returns the calculator's record, or None when the question is anything else (a story, a rounding question ...) or its
    answer is not a number: those answers stay as the concept card gives them and are labelled so.
    """
    text = str(question.get("text") or "")
    accepted = (rubric.get("answer_key") or {}).get("accept") or []
    division = _DIVIDE_QUESTION.match(text)
    if division and accepted:
        a, b = (division.group(1), division.group(2)) if division.group(1) else (division.group(3), division.group(4))
        try:
            result = calculator.divide_with_remainder(int(a.replace(",", "")), int(b.replace(",", "")))
        except calculator.CalculatorError:
            return None
        if not lp.answer_is_checkable(accepted[0]):
            return None
        return calculator.verify_claim(result, str(accepted[0]).strip())
    match = _BARE_CALCULATION.match(text)
    if not match or not accepted:
        return None
    a, unit_a, word, b, unit_b = match.groups()
    unit = (unit_a or unit_b or "").lower()
    if (unit_a or unit_b) and (word.lower() not in ("plus", "minus") or (unit_a or "").lower() != (unit_b or "").lower()):
        return None  # "3 tens times 4 tens" and mixed units are a different idea; leave them alone
    claim = _LEADING_NUMBER.match(str(accepted[0]))
    if not claim:
        return None
    claimed_unit = (claim.group(2) or "").strip().lower()
    if claimed_unit != unit:
        return None
    try:
        left, right = int(a.replace(",", "")), int(b.replace(",", ""))
        word = word.lower()
        if word == "plus":
            result = calculator.add(left, right)
        elif word == "minus":
            result = calculator.subtract(left, right)
        elif word == "times":
            result = calculator.multiply(left, right)
        else:
            if right == 0 or left % right:
                return None
            result = calculator.divide_exact(left, right)
    except calculator.CalculatorError:
        return None
    return calculator.verify_claim(result, int(claim.group(1).replace(",", "")))


# ------------------------------------------------------------------------------------------ does it fit the level?
_NUMERAL = re.compile(r"\d{1,3}(?:,\d{3})+|\d+")
_NUMERIC_ANSWER = re.compile(r"-?\d[\d,]*(?:\.\d+)?(?:\s+[A-Za-z][A-Za-z ]*)?")  # 37,901 / 7 ones / 1,204 miles
_BARE_CALCULATION_WORDS = 10  # "What is 12,490 plus 14,295?" is bare; a sentence of story around two numbers is not
_BARE_RECALL_WORDS = 8        # "What is a triangle?" is bare recall; a hard question in any lesson needs more than that
_HARD_MIN_WORDS = 15
_EASY_MAX_WORDS = 25
_BACK_REFERENCE = re.compile(r"\b(?:the same|as before|previous|above|earlier|last question|that answer|your answer)\b", re.I)


_GENERIC_TERMS = frozenset("use using find show with that this from each into their about solve name tell make what when they have also "
                           "like them then than your does give write draw look".split())
_QUESTION_OPERATIONS = {
    "add": r"\b(?:plus|add|adds|added|adding)\b|\+", "subtract": r"\b(?:minus|subtract\w*)\b|\u2212",
    "multiply": r"\b(?:times|multipl\w*)\b|\u00d7", "divide": r"\b(?:divided by|divid\w*)\b|\u00f7"}
_ARITHMETIC_BACK_REFERENCE = _BACK_REFERENCE
_PLAIN_BACK_REFERENCE = re.compile(r"\b(?:as before|previous|above|earlier|last question|that answer|your answer)\b", re.I)
_REASONING = re.compile(r"\b(?:why|explain|how do you know|because|compare|sort|tell\b.*\bapart|both|difference|which one)\b", re.I)


def _stem(word: str) -> str:
    return word[:-1] if word.endswith("s") and len(word) > 4 else word


def _key_terms(card: NormalizedConceptCard) -> list[str]:
    """The lesson's central concept as words: the content words of the first sentence of its objective."""
    text = card.objective.text
    first = re.split(r"(?<=[.!?])\s+", text.strip())[0]
    terms = [_stem(w) for w in re.findall(r"[a-z]+", first.lower()) if len(w) >= 4 and w not in _GENERIC_TERMS]
    if len(set(terms)) < 2:
        terms = [_stem(w) for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 4 and w not in _GENERIC_TERMS]
    return list(dict.fromkeys(terms))


def reuse_fit(card: NormalizedConceptCard, difficulty: str, question: dict[str, Any], rubric: dict[str, Any]) -> dict[str, Any]:
    """How well a concept-card question suits the level and the lesson goal, judged from its wording and answer only.

    Four criteria, applied to every lesson alike (no model, no meaning):
      one_step       easy: a single step (at most two stated numbers; one short question).  Hard: ``multi_step`` instead:
                     needs two or more steps, or a story/reasoning to interpret.
      central_concept  it tests the lesson goal: it shares key words with the first sentence of the objective, or (in a
                     calculation lesson) it asks for the result of a taught operation.
      stands_alone   it does not point back to an earlier question or answer.
      taught_operation  if it uses an operation word, the lesson teaches that operation (not applicable otherwise).
    tier 0 = every applicable criterion holds, 1 = one fails, 2 = more fail. A hard question that is not self-contained, a bare
    single-step calculation, or a bare recall question is rejected outright. A definition question is fine when it tests the goal.
    """
    text = str(question.get("text") or "")
    lowered = text.lower()
    first = str(((rubric.get("answer_key") or {}).get("accept") or [""])[0]).strip()
    arithmetic = bool(lp.taught_operations(card))
    numerals = len(_NUMERAL.findall(text))
    steps = max(0, numerals - 1)
    numeric_answer = lp._answer_shape(first) in ("integer", "decimal", "money", "fraction")
    words = len(text.split())
    answers = " ".join(str(a) for a in (rubric.get("answer_key") or {}).get("accept") or [])
    reasons = [f"{numerals} stated number(s), {words} word(s); answer is {'a number' if numeric_answer else 'not a number'}"]

    back = (_ARITHMETIC_BACK_REFERENCE if arithmetic else _PLAIN_BACK_REFERENCE).search(text)
    reasoning = bool(_REASONING.search(text))
    if difficulty == "hard":
        if back:
            return {"tier": 2, "reject": "not self-contained: it points back to an earlier question or answer", "reasons": reasons,
                    "criteria": {}, "overlap_terms": []}
        if arithmetic and numeric_answer and steps < 2 and words <= _BARE_CALCULATION_WORDS:
            return {"tier": 2, "reject": f"only one step in a bare calculation ({numerals} stated number(s)); a hard question "
                                         "needs at least two steps or a situation to interpret", "reasons": reasons, "criteria": {},
                    "overlap_terms": []}
        if not arithmetic and words <= _BARE_RECALL_WORDS and not reasoning:
            return {"tier": 2, "reject": "a bare recall question (a few words, no reasoning asked); a hard question needs more",
                    "reasons": reasons, "criteria": {}, "overlap_terms": []}
        step_ok = (steps >= 2 or words > _BARE_CALCULATION_WORDS) if arithmetic else (reasoning or words >= _HARD_MIN_WORDS)
        step_key = "multi_step"
    else:
        step_ok = (numerals <= 2) if arithmetic else (words <= _EASY_MAX_WORDS and text.count("?") <= 1)
        step_key = "one_step"

    terms = _key_terms(card)
    haystack = {_stem(w) for w in re.findall(r"[a-z]+", f"{lowered} {answers.lower()}")}
    overlap = [term for term in terms if term in haystack]
    overlap_ok = len(overlap) >= (1 if len(terms) <= 3 else 2)
    used = {name for name, pattern in _QUESTION_OPERATIONS.items() if re.search(pattern, lowered)}
    permitted = set(lp.permitted_operations(card))
    calculation_ok = arithmetic and numeric_answer and used <= permitted and (bool(used) or numerals >= 2)
    central = overlap_ok or calculation_ok
    criteria: dict[str, bool | None] = {step_key: step_ok, "central_concept": central, "stands_alone": not back,
                                        "taught_operation": (used <= permitted) if used else None}
    if not central:
        reasons.append(f"does not test the lesson's central concept (shares {len(overlap)} of the key words {terms[:6]} with the "
                       "objective, and is not a taught calculation)")
    if criteria["taught_operation"] is False:
        reasons.append(f"uses {sorted(used - permitted)}, which the lesson does not teach")
    if not step_ok:
        reasons.append("does not fit the level's step count" if difficulty != "hard" else "a hard question needs more than one step")
    failed = [name for name, ok in criteria.items() if ok is False]
    tier = 0 if not failed else 1 if len(failed) == 1 else 2
    digits = sum(len(n.replace(",", "")) for n in _NUMERAL.findall(text))
    simplicity = (-steps, words) if difficulty == "hard" else (digits, words)  # within equal scores: easy simplest, hard most steps
    return {"tier": tier, "reject": None, "reasons": reasons, "criteria": criteria, "overlap_terms": overlap, "simplicity": list(simplicity)}


def _natural(value: Any) -> list:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", str(value))]


def reuse_candidates(card: NormalizedConceptCard, difficulty: str) -> dict[str, Any]:
    """Concept-card questions that may stand in for a question at this difficulty, best first.

    Returns {'rule', 'eligible': [candidate...], 'rejected': {question_id: reason}}. A candidate is
    {'question', 'rubric', 'position', 'asset_blockers', 'uncertainty'}.
    """
    kind = REUSE_KIND.get(difficulty)
    if kind is None:
        return {"rule": _NO_KIND_RULE, "eligible": [], "rejected": {}}
    rule = (f"{difficulty}: a {kind!r} question with an exact-answer rubric"
            + (", from a section that also holds a taught explanation or example" if difficulty == "easy" else ""))
    rubrics = {rubric.get("id"): rubric for rubric in card.reference_rubrics}
    sections = _teaching_sections(card)
    eligible, rejected = [], {}
    for position, question in enumerate(card.reference_questions):
        if question.get("kind") != kind:
            continue
        qid = question.get("id")
        rubric = rubrics.get(question.get("rubric_id"))
        if rubric is None:
            rejected[qid] = f"its rubric {question.get('rubric_id')!r} is not in the card"
        elif (rubric.get("answer_key") or {}).get("mode") != "exact" or not (rubric["answer_key"].get("accept")):
            rejected[qid] = f"its rubric answer key is {(rubric.get('answer_key') or {}).get('mode')!r}, not an exact answer list"
        elif difficulty == "easy" and sections and section_family((question.get("source_ref") or {}).get("section")) not in sections:
            rejected[qid] = (f"its source section {(question.get('source_ref') or {}).get('section')!r} "
                             "is not a section that holds a taught explanation or example")
        else:
            fit = reuse_fit(card, difficulty, question, rubric)
            if fit["reject"]:
                rejected[qid] = fit["reject"]
                continue
            check = verify_reused_answer(question, rubric)
            if check and not check["matches"]:
                rejected[qid] = (f"its accepted answer {check['claimed']} disagrees with the calculator, which gets "
                                 f"{check['computed']}; the concept card's stored answer looks wrong")
                continue
            problems = asset_problems(card, list(question.get("asset_ids") or []))
            eligible.append({"question": question, "rubric": rubric, "position": position, "fit": fit, "answer_check": check,
                             "asset_blockers": list(problems), "asset_problems": problems,
                             "uncertainty": uncertainty_signals(card, question, rubric)})
    # Best fit to the level and the lesson goal first, then the fewest readiness blockers, then (within equal scores) the simplest
    # for easy or the most steps for hard. The last tie is broken by question id in natural order, never by card position.
    eligible.sort(key=lambda c: (c["fit"]["tier"], -len(c["fit"]["overlap_terms"]), len(c["asset_blockers"]) + len(c["uncertainty"]),
                                 c["fit"].get("simplicity", []), _natural(c["question"].get("id"))))
    return {"rule": rule, "eligible": eligible, "rejected": rejected}


def plan_reuse(card: NormalizedConceptCard, *, allow_asset_blocked: bool = True) -> dict[str, dict[str, Any]]:
    """Per level: the chosen reusable item (or None), its ranked alternatives and why others were rejected."""
    plan = {}
    for level in LEVELS:
        found = reuse_candidates(card, level)
        eligible = found["eligible"]
        if not allow_asset_blocked:
            eligible = [c for c in eligible if not c["asset_blockers"]]
        plan[level] = {"choice": eligible[0] if eligible else None, "rule": found["rule"], "rejected": found["rejected"],
                       "eligible_in_rank_order": [c["question"]["id"] for c in eligible]}
    return plan


def reused_response_type(rubric: dict[str, Any]) -> str:
    """The concept card's questions have no response type, so it is read from the first accepted answer."""
    first = str(((rubric.get("answer_key") or {}).get("accept") or [""])[0]).strip()
    number = r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"  # plain, or with thousands separators as the grade-4 cards write them
    return "numeric_short" if re.fullmatch(number, first) else "short_text"


def reused_stimulus(card: NormalizedConceptCard, question: dict[str, Any]) -> dict[str, Any]:
    asset_ids = list(question.get("asset_ids") or [])
    if not asset_ids:
        return {"kind": "none"}
    asset = _asset(card, asset_ids[0]) or {}
    state = str(asset.get("description") or f"asset {asset_ids[0]}").strip().rstrip(".")
    values = question.get("stimulus")
    if isinstance(values, dict) and values:
        state += "; question values: " + ", ".join(f"{key.replace('_', ' ')} {value}" for key, value in values.items())
    return {"kind": "visual_asset", "asset_ref": ref("concept_card", asset_ids[0]), "state": state}


def stimulus_for_generated() -> dict[str, Any]:
    """Generated prompts are text only; the task givens stay in verification, never as a delivered stimulus."""
    return {"kind": "none"}


# --------------------------------------------------------------------------------------------------------- hints
def hint_refs_for_teaching(card: NormalizedConceptCard, teaching_ids: list[str]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Hints the card itself ties to these teaching items, or a stated gap.

    The only link the card data offers is an asset: a teaching item and a card question that show the same asset.
    The link is used only when every practice/application question sharing the item's assets uses the same hint
    list. Anything less clean is reported, not guessed.
    """
    items = {item.id: item for item in (*card.explanations, *card.examples) if item.id}
    refs: list[dict[str, str]] = []
    reasons: dict[str, str] = {}
    for teaching_id in teaching_ids:
        item = items.get(teaching_id)
        if item is None:
            continue  # the objective, or an unknown id
        if not item.asset_ids:
            reasons[teaching_id] = "the teaching item has no asset, so no card question can be linked to it"
            continue
        linked = [q for q in card.reference_questions
                  if q.get("kind") in ("practice", "application") and set(q.get("asset_ids") or []) & set(item.asset_ids)]
        hint_sets = {tuple(q.get("hint_ids") or ()) for q in linked}
        if not linked:
            reasons[teaching_id] = "no practice or application question shares its assets"
        elif len(hint_sets) > 1:
            reasons[teaching_id] = (f"{len(linked)} questions share its assets but use {len(hint_sets)} different hint sets")
        else:
            for hint_id in next(iter(hint_sets)):
                if hint_id not in {r["id"] for r in refs}:
                    refs.append(ref("concept_card", hint_id))
    checked = [t for t in teaching_ids if t in items]
    status = "wired" if refs and not reasons else "unresolved" if reasons else "none"
    if reasons and refs:
        status = "partial"
    return refs, {"status": status, "checked": checked, "reasons": reasons}


# ----------------------------------------------------------------------------------------------------- readiness
def blocking_issues_for_reuse(card: NormalizedConceptCard, question_id: str, candidate: dict[str, Any]) -> list[str]:
    qid = candidate["question"]["id"]
    rid = candidate["rubric"]["id"]
    issues = []
    for asset_id, reason in candidate["asset_problems"].items():
        if reason == "not listed in assets_required":
            issues.append(f"{question_id} stimulus asset {asset_id} is not listed in the concept card's assets_required")
        else:
            issues.append(f"{question_id} stimulus asset {asset_id} has no usable description in the concept card (missing: {reason})")
    fit = candidate.get("fit") or {}
    if (fit.get("criteria") or {}).get("central_concept") is False:
        issues.append(f"{question_id} reuses {qid}, which does not test the lesson's central concept (it shares too few key words "
                      "with the objective and is not a taught calculation); check that it suits the level")
    for signal in candidate["uncertainty"]:
        flags = ", ".join(signal["flag_ids"])
        if signal["kind"] == "named_in_review_flags":
            issues.append(f"{question_id} reuses {qid}, which the concept card's review_flags name ({flags})")
        else:
            issues.append(f"{question_id} reuses {qid}, whose accepted answer is derived, not printed in the source "
                          f"(rubric {rid} origin 'derived'" + (f"; review_flags {flags} ask for a spot-check)" if flags else ")"))
    return issues


def compute_readiness(card: NormalizedConceptCard, reused: list[tuple[str, dict[str, Any]]], review_status: str,
                      missing_levels: list[str] | None = None, missing_reasons: dict[str, str] | None = None,
                      grounding_only: list[str] | None = None) -> dict[str, Any]:
    """reused: [(assessment question id, candidate)] in question order.

    Signals: the card is draft; a difficulty level is missing (a 2-of-3 card names it, CLAUDE.md section 6); a reused
    question's asset has no usable description; a reused question's answer is flagged or derived.
    """
    issues = [DRAFT_BLOCKER] if review_status == "draft" else []
    levels_present = len(LEVELS) - len(missing_levels or [])
    for level in missing_levels or []:
        reason = (missing_reasons or {}).get(level)
        issues.append(f"card has {levels_present} of 3 difficulty levels; {level} is missing" + (f" ({reason})" if reason else ""))
    for question_id, candidate in reused:
        issues += blocking_issues_for_reuse(card, question_id, candidate)
    for question_id in grounding_only or []:
        issues.append(f"{question_id} is grounding only: its answer is not verified by code (the lesson has nothing code can "
                      "check) and needs review before use")
    return {"ready_for_delivery": not issues, "blocking_issues": issues}


# ----------------------------------------------------------------------------------------------- generated items
def _grounding_ids(proposal: dict[str, Any], objective_id: str | None) -> list[str]:
    return [item_id for item_id in proposal.get("teaching_refs", []) if item_id != objective_id]


def _part_letters(count: int) -> str:
    return "abcdefghijklmnopqrstuvwxyz"[:count]


def generated_prompt(proposal: dict[str, Any]) -> str:
    """The learner-facing text. A multi-part proposal is flattened to its headline plus its lettered parts."""
    if proposal.get("response_type") != "multi_part":
        return proposal["prompt"]
    parts = proposal["answer_parts"]
    letters = _part_letters(len(parts))
    return proposal["prompt"] + " Answer each part. " + " ".join(f"({letters[i]}) {part['prompt']}" for i, part in enumerate(parts))


def generated_rubric(rubric_id: str, proposal: dict[str, Any]) -> dict[str, Any]:
    """A this_card rubric from the verified answer(s), written with the concept cards' own answer-key pattern."""
    kind = proposal.get("response_type")
    accepted = proposal.get("accepted_answers")
    if kind in ("number", "short_text"):
        answer = proposal["expected_answer"]
        if accepted:
            accept = list(accepted)
        elif kind == "number" and isinstance(answer, int) and not isinstance(answer, bool):
            accept = number_forms(answer)  # whole numbers: the corpus' own spelling pattern
        else:
            raise AssemblyError(f"a {kind} answer needs its accepted spellings; the proposal has none")
        grounded = proposal.get("answer_verification") == "grounding_only"
        numeric = kind == "number"
        return {"id": rubric_id, "answer_key": {"mode": "exact", "accept": accept},
                "partial_credit_eligible": False,
                "correct": (proposal.get("marking_criteria") if grounded and proposal.get("marking_criteria") else f"Says {answer}."),
                "partial": None,
                "incorrect": f"Gives a clear number that is not {answer}." if numeric else "Gives a clear answer that is not correct.",
                "unclear": "No number can be understood from the response." if numeric else "No answer can be understood from the response.",
                "origin": "generated"}
    if kind == "multi_part":
        task = proposal.get("task") or {}
        parts = proposal["answer_parts"]
        final = next((part for part in parts if part["id"] == task.get("final_part_id")), None)
        if final is None:
            raise AssemblyError("a multi-part proposal needs its task.final_part_id to name an answer part")
        letters = _part_letters(len(parts))
        listed = "; ".join(f"part ({letters[i]}) is {part['expected_answer']}" for i, part in enumerate(parts))
        return {"id": rubric_id, "answer_key": {"mode": "exact", "accept": number_forms(final["expected_answer"])},
                "partial_credit_eligible": True, "correct": f"Gets all {len(parts)} parts right: {listed}.",
                "partial": f"Gets at least one part right but not all {len(parts)}: {listed}.",
                "incorrect": "Gives clear numbers but none of the parts is right.",
                "unclear": "No number can be understood from the response.", "origin": "generated"}
    raise AssemblyError(f"cannot build an exact-answer rubric for response_type {kind!r}")


def _custom_routes(follow_up_id: str | None, partial_eligible: bool, incomplete_id: str | None = None) -> dict[str, str]:
    routes = {"correct": DEFAULT_OUTCOME_ROUTES["correct"]}
    if partial_eligible:
        routes["partial"] = DEFAULT_OUTCOME_ROUTES["partial"]
    routes["incorrect"] = (f"give_followup_{follow_up_id}_then_bottom_out" if follow_up_id
                           else DEFAULT_OUTCOME_ROUTES["incorrect"])
    if incomplete_id:  # some parts attempted, not all: distinct from incorrect (fully attempted) and unclear (unparseable)
        routes["incomplete"] = f"give_followup_{incomplete_id}_then_bottom_out"
    routes["unclear"] = DEFAULT_OUTCOME_ROUTES["unclear"]
    return routes


def _response_type(proposal: dict[str, Any]) -> str:
    kind = proposal.get("response_type")
    if kind == "number":
        return "numeric_short"
    if kind == "short_text":
        return "short_text"
    if kind == "multi_part":
        return "multi_part"  # not in the target example's vocabulary; the target has no multi-step shape yet
    raise AssemblyError(f"unsupported generated response_type {kind!r}")


def require_verification(proposal: dict[str, Any], where: str) -> str:
    """How a generated answer was verified, refusing any claim the proposal cannot back.

    'code' needs the calculator's record with a match; 'grounding_only' is honest for lessons code cannot check. A proposal
    with no label, or one that says 'code' without the record, is refused: nothing unverified may look verified.
    """
    label = proposal.get("answer_verification")
    if label == "code":
        check = (proposal.get("verification") or {}).get("answer_check")
        if not isinstance(check, dict) or check.get("matches") is not True and not (
                check.get("matches") is None and check.get("computed") is not None):
            raise AssemblyError(f"{where}: the proposal says its answer was verified by code but has no matching code verification "
                                "record (verification.answer_check); a calculation question that skipped the code verification "
                                "cannot be used")
        return "code"
    if label == "grounding_only":
        return "grounding_only"
    raise AssemblyError(f"{where}: the proposal has no recognised answer_verification ({label!r}); it cannot be assembled")


def _generated_question(card: NormalizedConceptCard, question_id: str, difficulty: str, proposal: dict[str, Any],
                        hint_refs: list[dict[str, str]], follow_up_id: str | None, incomplete_id: str | None = None) -> dict[str, Any]:
    rubric_id = f"r_{question_id}"
    question = {
        "id": question_id, "difficulty": difficulty, "origin": "generated",
        "grounded_in": [ref("concept_card", item_id) for item_id in _grounding_ids(proposal, card.objective.id)],
        "prompt": generated_prompt(proposal), "response_type": _response_type(proposal),
        "answer_verification": require_verification(proposal, question_id),
        "stimulus": stimulus_for_generated(), "rubric_ref": ref("this_card", rubric_id), "hint_refs": hint_refs}
    if follow_up_id or incomplete_id:
        question["max_attempts"] = MAX_ATTEMPTS_DEFAULT
        question["follow_up_ref"] = ref("this_card", follow_up_id or incomplete_id)
        question["routes"] = _custom_routes(follow_up_id, proposal["response_type"] == "multi_part", incomplete_id)
    else:
        question["routes"] = "default"
    return question


def _reused_question(card: NormalizedConceptCard, question_id: str, difficulty: str, candidate: dict[str, Any]) -> dict[str, Any]:
    source, rubric = candidate["question"], candidate["rubric"]
    return {
        "id": question_id, "difficulty": difficulty, "origin": "reused",
        "question_ref": ref("concept_card", source["id"]), "response_type": reused_response_type(rubric),
        "answer_verification": "code" if candidate.get("answer_check") else "concept_card_unverified",
        "stimulus": reused_stimulus(card, source), "rubric_ref": ref("concept_card", rubric["id"]),
        "hint_refs": [ref("concept_card", hint_id) for hint_id in source.get("hint_ids", [])], "routes": "default"}


def _follow_up(card: NormalizedConceptCard, parent_id: str, proposal: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    follow_up_id = f"fu_{parent_id}"
    grounded = _grounding_ids(proposal, card.objective.id)
    hints, wiring = hint_refs_for_teaching(card, grounded)
    follow_up = {
        "id": follow_up_id, "triggered_by": {"question_id": parent_id, "outcome": "incorrect"},
        "grounded_in": [ref("concept_card", item_id) for item_id in grounded],
        "prompt": FOLLOW_UP_PREFIX + generated_prompt(proposal), "response_type": _response_type(proposal),
        "answer_verification": require_verification(proposal, follow_up_id),
        "stimulus": stimulus_for_generated(), "rubric_ref": ref("this_card", f"r_{follow_up_id}"),
        "hint_refs": hints, "max_attempts": 1, "on_resolved": f"return_to_{parent_id}_then_bottom_out"}
    return follow_up, generated_rubric(f"r_{follow_up_id}", proposal), wiring


def _incomplete_follow_up(card: NormalizedConceptCard, parent_id: str, proposal: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """The follow-up for an incomplete multi-part answer: the first verified part, asked on its own.

    Proposed design (the brief only says an incomplete answer needs its own follow-up that isolates the step that broke
    down): it needs no model, and its answer key is the part's already-verified value.
    """
    first = proposal["answer_parts"][0]
    follow_up_id = f"fu_{parent_id}_incomplete"
    grounded = _grounding_ids(proposal, card.objective.id)
    hints, wiring = hint_refs_for_teaching(card, grounded)
    follow_up = {
        "id": follow_up_id, "triggered_by": {"question_id": parent_id, "outcome": "incomplete"},
        "grounded_in": [ref("concept_card", item_id) for item_id in grounded],
        "prompt": INCOMPLETE_PREFIX + first["prompt"], "response_type": "numeric_short",
        "answer_verification": require_verification(proposal, follow_up_id),
        "stimulus": stimulus_for_generated(), "rubric_ref": ref("this_card", f"r_{follow_up_id}"),
        "hint_refs": hints, "max_attempts": 1, "on_resolved": f"return_to_{parent_id}_then_bottom_out"}
    rubric = generated_rubric(f"r_{follow_up_id}", {"response_type": "number", "expected_answer": first["expected_answer"]})
    return follow_up, rubric, wiring


def _numbers_in(text: str) -> set[int]:
    return {int(n) for n in re.findall(r"(?<![\d.,])\d+(?![\d.,]*\d)", text or "")}


def _audit_record(proposal: dict[str, Any]) -> dict[str, Any]:
    keep = ("id", "run_id", "served_by", "status", "review_flags", "difficulty_rationale", "teaching_refs", "answer_verification",
            "verification", "task")
    return {key: copy.deepcopy(proposal[key]) for key in keep if key in proposal}


def assemble_card(card: NormalizedConceptCard, choices: dict[str, dict[str, Any]],
                  followups: dict[str, dict[str, Any]] | None = None, *, card_version: int = 1,
                  source: dict[str, Any] | None = None,
                  missing_reasons: dict[str, str] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (assessment card in the target structure, audit record kept beside it).

    missing_reasons[level] is an optional plain-language reason a missing level could not be produced; it is appended to
    that level's readiness issue.

    choices[level] is {'origin': 'reused', 'candidate': <reuse_candidates item>} or
    {'origin': 'generated', 'proposal': <verified generator proposal>} for every level.
    followups[level] is {'proposal': ...} or {'error': 'why'} for a generated question that should have a scaffold.
    The audit record keeps what the target has no place for: verification, task, run IDs, review flags and notes.
    """
    followups = followups or {}
    present = [level for level in LEVELS if level in choices]
    if len(present) < MIN_LEVELS:
        raise AssemblyError(f"a card needs at least {MIN_LEVELS} of the 3 difficulty levels; got {len(present)}"
                            + (f" ({', '.join(present)})" if present else ""))
    questions, follow_ups, rubrics, reused = [], [], [], []
    audit: dict[str, Any] = {"source": source or {}, "questions": {}, "follow_ups": {}, "notes": []}
    if len(present) < len(LEVELS):
        audit["notes"].append(f"card has {len(present)} of 3 levels ({', '.join(present)}); "
                              f"missing: {', '.join(l for l in LEVELS if l not in present)}")
    for level in present:
        choice = choices[level]
        question_id = f"aq_{LEVEL_CODE[level]}_01"
        if choice["origin"] == "reused":
            candidate = choice["candidate"]
            questions.append(_reused_question(card, question_id, level, candidate))
            reused.append((question_id, candidate))
            question_assets = list(candidate["question"].get("asset_ids") or [])
            audit["questions"][question_id] = {
                "origin": "reused", "concept_card_question": candidate["question"]["id"], "concept_card_rubric": candidate["rubric"]["id"],
                "asset_blockers": candidate["asset_blockers"], "uncertainty": candidate["uncertainty"],
                "other_assets_of_the_question": question_assets[1:]}
            continue
        proposal = choice["proposal"]
        hints, wiring = hint_refs_for_teaching(card, _grounding_ids(proposal, card.objective.id))
        outcome = followups.get(level) if level in FOLLOW_UP_LEVEL else None
        follow_up_id = None
        if outcome and "proposal" in outcome:
            follow_up, follow_up_rubric, follow_wiring = _follow_up(card, question_id, outcome["proposal"])
            follow_up_id = follow_up["id"]
            audit["follow_ups"][follow_up_id] = {**_audit_record(outcome["proposal"]), "hint_wiring": follow_wiring}
            if follow_wiring["status"] != "wired":
                audit["notes"].append(f"{follow_up_id} hints: {follow_wiring['status']} "
                                      f"({'; '.join(f'{k}: {v}' for k, v in follow_wiring['reasons'].items()) or 'no teaching item to link'})")
        elif level in FOLLOW_UP_LEVEL:
            reason = (outcome or {}).get("error", "no follow-up was requested")
            audit["notes"].append(f"{question_id} has no follow-up ({reason}); it uses the default routes")
        incomplete_id = None
        if proposal.get("response_type") == "multi_part" and proposal.get("answer_parts"):
            incomplete, incomplete_rubric, incomplete_wiring = _incomplete_follow_up(card, question_id, proposal)
            incomplete_id = incomplete["id"]
            audit["follow_ups"][incomplete_id] = {"built": "from the first verified answer part; no model call",
                                                  "part_id": proposal["answer_parts"][0]["id"], "hint_wiring": incomplete_wiring}
        question = _generated_question(card, question_id, level, proposal, hints, follow_up_id, incomplete_id)
        questions.append(question)
        rubrics.append(generated_rubric(f"r_{question_id}", proposal))
        if follow_up_id:
            follow_ups.append(follow_up)
            rubrics.append(follow_up_rubric)
        if incomplete_id:
            follow_ups.append(incomplete)
            rubrics.append(incomplete_rubric)
        audit["questions"][question_id] = {"origin": "generated", "proposal": _audit_record(proposal), "hint_wiring": wiring}
        if wiring["status"] != "wired":
            audit["notes"].append(f"{question_id} hints: {wiring['status']} ({'; '.join(f'{k}: {v}' for k, v in wiring['reasons'].items()) or 'no teaching item to link'})")
    # Numbers shared between a generated question and a reused one are reported (the reuse path cannot enforce distinctness).
    from question_generator import proposal_quantities
    for question_id, entry in audit["questions"].items():
        if entry["origin"] != "generated":
            continue
        proposal = choices[next(level for level in present if f"aq_{LEVEL_CODE[level]}_01" == question_id)]["proposal"]
        quantities = proposal_quantities(proposal)
        mine = set(quantities["inputs"]) | set(quantities["values"])
        for other_id, other in audit["questions"].items():
            if other["origin"] != "reused":
                continue
            theirs = next(c for qid, c in reused if qid == other_id)
            reused_numbers = _numbers_in(theirs["question"].get("text", ""))
            reused_numbers |= {int(a) for a in theirs["rubric"]["answer_key"]["accept"] if re.fullmatch(r"\d+", str(a))}
            shared = sorted(mine & reused_numbers)
            if shared:
                audit["notes"].append(f"{question_id} shares numbers {shared} with reused {other_id}; "
                                      "distinctness against concept-card questions is reported, not enforced")
    card_dict = {
        "schema_version": SCHEMA_VERSION, "card_type": CARD_TYPE,
        "assessment_card_id": f"assess_{card.concept_id}_v{card_version}", "card_version": card_version,
        "review_status": "draft",
        "linked_concept": {"concept_id": card.concept_id, "concept_version": card.card_version},
        "subject": card.subject, "grade": card.grade, "objective_refs": [card.objective.id],
        "provenance": {"generated_by": GENERATED_BY, "reuse_policy": REUSE_POLICY},
        "readiness": compute_readiness(card, reused, "draft", missing_levels=[l for l in LEVELS if l not in present],
                                      missing_reasons=missing_reasons,
                                      grounding_only=[qid for qid, entry in audit["questions"].items()
                                                      if entry.get("proposal", {}).get("answer_verification") == "grounding_only"]),
        "difficulty_levels": present, "max_attempts_default": MAX_ATTEMPTS_DEFAULT,
        "default_outcome_routes": dict(DEFAULT_OUTCOME_ROUTES), "fallback_rules": dict(FALLBACK_RULES),
        "questions": questions, "follow_ups": follow_ups, "rubrics": rubrics}
    audit["assessment_card_id"] = card_dict["assessment_card_id"]
    problems = check_card(card_dict, card)
    if problems:
        raise AssemblyError("assembled card fails its structure check: " + "; ".join(problems))
    return card_dict, audit


# ------------------------------------------------------------------------------------------------ structure check
TOP_LEVEL_KEYS = ("schema_version", "card_type", "assessment_card_id", "card_version", "review_status", "linked_concept",
                  "subject", "grade", "objective_refs", "provenance", "readiness", "difficulty_levels",
                  "max_attempts_default", "default_outcome_routes", "fallback_rules", "questions", "follow_ups", "rubrics")
# answer_verification is an addition to the target's question vocabulary, requested by the owner: how each answer was verified.
#   code                    computed by code (calculator.py) and recorded
#   grounding_only          not verifiable by code; only grounded in the concept card's own text. Needs human review.
#   concept_card_unverified a reused question whose answer comes from the concept card and could not be re-derived by code
ANSWER_VERIFICATION = ("code", "grounding_only", "concept_card_unverified")
REUSED_QUESTION_KEYS = ("id", "difficulty", "origin", "question_ref", "response_type", "answer_verification", "stimulus",
                        "rubric_ref", "hint_refs", "routes")
GENERATED_QUESTION_KEYS = ("id", "difficulty", "origin", "grounded_in", "prompt", "response_type", "answer_verification",
                           "stimulus", "rubric_ref", "hint_refs", "max_attempts", "follow_up_ref", "routes")
FOLLOW_UP_KEYS = ("id", "triggered_by", "grounded_in", "prompt", "response_type", "answer_verification", "stimulus",
                  "rubric_ref", "hint_refs", "max_attempts", "on_resolved")
RUBRIC_KEYS = ("id", "answer_key", "partial_credit_eligible", "correct", "partial", "incorrect", "unclear", "origin")
SCOPES = ("concept_card", "this_card")


def check_card(card: dict[str, Any], concept: NormalizedConceptCard) -> list[str]:
    """Problems found in an assembled card: field names/nesting against the target, and every reference resolving."""
    problems: list[str] = []
    if tuple(card) != TOP_LEVEL_KEYS:
        problems.append(f"top-level keys differ from the target: {list(card)}")
    levels = card.get("difficulty_levels")
    asked = [q.get("difficulty") for q in card.get("questions", [])]
    if levels != asked or len(levels or []) < MIN_LEVELS or any(l not in LEVELS for l in levels or []):
        problems.append(f"difficulty_levels {levels} must list the questions' levels {asked}, at least {MIN_LEVELS} of {list(LEVELS)}")
    this_rubrics = {r.get("id") for r in card.get("rubrics", [])}
    this_follow_ups = {f.get("id") for f in card.get("follow_ups", [])}
    concept_ids = {
        "question": {q.get("id") for q in concept.reference_questions}, "rubric": {r.get("id") for r in concept.reference_rubrics},
        "hint": {h.get("id") for h in concept.reference_hints}, "asset": {a.get("asset_id") for a in concept.required_assets},
        "teaching": {i.id for i in (*concept.explanations, *concept.examples)} | {concept.objective.id}
                    | {q.get("id") for q in concept.reference_questions} | {m.get("id") for m in concept.misconceptions}}
    seen: set[str] = set()

    def check_ref(value: Any, kind: str, where: str) -> None:
        if not isinstance(value, dict) or set(value) != {"scope", "id"}:
            problems.append(f"{where}: a reference must be exactly {{scope, id}}")
            return
        if value["scope"] not in SCOPES:
            problems.append(f"{where}: unknown scope {value['scope']!r}")
        elif value["scope"] == "concept_card" and value["id"] not in concept_ids[kind]:
            problems.append(f"{where}: {value['id']} is not a {kind} in the concept card")
        elif value["scope"] == "this_card":
            known = this_rubrics if kind == "rubric" else this_follow_ups if kind == "follow_up" else set()
            if value["id"] not in known:
                problems.append(f"{where}: {value['id']} is not a {kind} in this card")

    for item in (*card.get("questions", []), *card.get("follow_ups", []), *card.get("rubrics", [])):
        if item.get("id") in seen:
            problems.append(f"duplicate id {item.get('id')}")
        seen.add(item.get("id"))
    for question in card.get("questions", []):
        where = question.get("id", "?")
        keys = tuple(question)
        if question.get("origin") == "reused":
            shapes = (REUSED_QUESTION_KEYS,)
        else:  # a generated question has both attempt/follow-up fields or neither
            shapes = (GENERATED_QUESTION_KEYS, tuple(k for k in GENERATED_QUESTION_KEYS if k not in ("max_attempts", "follow_up_ref")))
        if keys not in shapes:
            problems.append(f"{where}: question keys {list(keys)} do not match the target shape for origin {question.get('origin')!r}")
        if question.get("origin") == "reused":
            check_ref(question.get("question_ref"), "question", f"{where}.question_ref")
        else:
            for index, grounded in enumerate(question.get("grounded_in", [])):
                check_ref(grounded, "teaching", f"{where}.grounded_in[{index}]")
            if "follow_up_ref" in question:
                check_ref(question["follow_up_ref"], "follow_up", f"{where}.follow_up_ref")
        check_ref(question.get("rubric_ref"), "rubric", f"{where}.rubric_ref")
        for index, hint in enumerate(question.get("hint_refs", [])):
            check_ref(hint, "hint", f"{where}.hint_refs[{index}]")
        stimulus = question.get("stimulus", {})
        if stimulus.get("kind") == "visual_asset":
            check_ref(stimulus.get("asset_ref"), "asset", f"{where}.stimulus.asset_ref")
        elif stimulus.get("kind") != "none":
            problems.append(f"{where}: stimulus kind {stimulus.get('kind')!r} is not in the target vocabulary")
        routes = question.get("routes")
        if isinstance(routes, dict):
            for name, text in routes.items():
                if "give_followup_" in text:
                    named = text[len("give_followup_"):-len("_then_bottom_out")]
                    if named not in this_follow_ups:
                        problems.append(f"{where}.routes.{name}: follow-up {named} is not in this card")
        elif routes != "default":
            problems.append(f"{where}: routes must be 'default' or an object")
    for follow_up in card.get("follow_ups", []):
        where = follow_up.get("id", "?")
        if tuple(follow_up) != FOLLOW_UP_KEYS:
            problems.append(f"{where}: follow-up keys {list(follow_up)} differ from the target")
        check_ref(follow_up.get("rubric_ref"), "rubric", f"{where}.rubric_ref")
        for index, grounded in enumerate(follow_up.get("grounded_in", [])):
            check_ref(grounded, "teaching", f"{where}.grounded_in[{index}]")
        for index, hint in enumerate(follow_up.get("hint_refs", [])):
            check_ref(hint, "hint", f"{where}.hint_refs[{index}]")
    for rubric in card.get("rubrics", []):
        where = rubric.get("id", "?")
        if tuple(rubric) != RUBRIC_KEYS:
            problems.append(f"{where}: rubric keys {list(rubric)} differ from the target")
        key = rubric.get("answer_key", {})
        if key.get("mode") == "exact" and not (isinstance(key.get("accept"), list) and key["accept"]
                                               and all(isinstance(a, str) and a for a in key["accept"])):
            problems.append(f"{where}: an exact answer_key needs a non-empty accept list of strings")
    return problems
