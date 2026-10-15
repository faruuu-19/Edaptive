"""Typed task kinds whose answers come from calculator.py, never from the model.

The model chooses a kind, a template and the givens; this module checks them, renders the learner wording from a fixed
template, and computes the answer with the calculator. Easy may use any template; medium needs a situation template.
Hard is not built for these kinds (hard stays the integer multi-part chain in question_generator).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from typing import Any, Callable

import calculator as calc
import task_contract
from calculator import CalculatorError

VERSION = "bounded-maths-task-v1"
ENVELOPE = {"version", "kind", "givens", "milestones", "template", "final_part_id"}


@dataclass(frozen=True)
class Template:
    text: str
    situation: bool = False
    check: Callable[[dict], str | None] | None = None   # parsed givens -> problem text
    mode: str = ""                                       # which answer a kind with several answers should give


@dataclass(frozen=True)
class Kind:
    domain: str                      # integer | fraction | decimal | money | rule
    roles: dict                      # role -> given type
    templates: dict
    compute: Callable[[dict, str], calc.Calculation] = field(repr=False, default=None)


@dataclass(frozen=True)
class Rendered:
    kind: str
    answer: calc.Calculation
    answer_type: str                 # integer | remainder | fraction | decimal | money | symbol
    response_type: str               # number | short_text
    prompt: str
    accept: list | None              # None: the assembler writes the whole-number spellings
    stimulus: dict
    situation: bool
    domain: str
    givens: dict                     # as parsed (Fractions, Decimals ...)
    template: str


# ------------------------------------------------------------------------------------------------ given parsing
def _count(value: Any, role: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"given {role} must be a whole number of at least {minimum}")
    return value


def _fraction(value: Any, role: str) -> Fraction:
    if not isinstance(value, str) or "/" not in value:
        raise ValueError(f"given {role} must be a fraction written as a string such as '3/4'")
    try:
        parsed = calc.parse_fraction(value)
    except CalculatorError as exc:
        raise ValueError(f"given {role}: {exc}") from None
    if parsed <= 0:
        raise ValueError(f"given {role} must be a positive fraction")
    return parsed


def _decimal(value: Any, role: str) -> Decimal:
    if not isinstance(value, str) or "." not in value:
        raise ValueError(f"given {role} must be a decimal written as a string such as '2.5'")
    try:
        parsed = calc.parse_decimal(value)
    except CalculatorError as exc:
        raise ValueError(f"given {role}: {exc}") from None
    if parsed < 0:
        raise ValueError(f"given {role} must not be negative")
    return parsed


def _money(value: Any, role: str) -> Decimal:
    if isinstance(value, (bool, float)) or not isinstance(value, (str, int)):
        raise ValueError(f"given {role} must be an amount of money written as a string such as '$3.50'")
    try:
        parsed = calc.parse_money(value)
    except CalculatorError as exc:
        raise ValueError(f"given {role}: {exc}") from None
    if parsed < 0:
        raise ValueError(f"given {role} must not be negative")
    return parsed


def _number(value: Any, role: str) -> Any:
    """For comparison: a whole number, or a decimal / fraction / money string. Returns what the calculator accepts."""
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"given {role} must be a whole number or a string such as '0.5' or '3/4'")
    if isinstance(value, int):
        if value < 0:
            raise ValueError(f"given {role} must not be negative")
        return value
    if isinstance(value, str):
        try:
            calc.compare(value, value)
        except CalculatorError as exc:
            raise ValueError(f"given {role}: {exc}") from None
        return value.strip()
    raise ValueError(f"given {role} is not a number")


def _place(value: Any, role: str) -> int:
    try:
        return calc._power_of_ten(_count(value, role, 1))
    except CalculatorError as exc:
        raise ValueError(f"given {role}: {exc}") from None


def _places(value: Any, role: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 2:
        raise ValueError(f"given {role} must be 0, 1 or 2 decimal places")
    return value


_PARSERS = {"count": lambda v, r: _count(v, r, 1), "whole": lambda v, r: _count(v, r, 2), "fraction": _fraction,
            "decimal": _decimal, "money": _money, "number": _number, "place": _place, "places": _places,
            "dividend": lambda v, r: _count(v, r, 1), "divisor": lambda v, r: _count(v, r, 2)}


# ------------------------------------------------------------------------------------------------- show givens
def _show(kind_type: str, value: Any) -> str:
    if kind_type == "fraction":
        return calc.format_fraction(value)
    if kind_type == "decimal":
        return format(value, "f")
    if kind_type == "money":
        return calc.format_money(value)
    return str(value)


_UNIT = {0: "whole number", 1: "tenth", 2: "hundredth"}
_PLACE_UNIT = {"ones": "one", "tens": "ten", "hundreds": "hundred", "thousands": "thousand", "ten thousands": "ten thousand",
               "hundred thousands": "hundred thousand", "millions": "million"}


# ------------------------------------------------------------------------------------------------ constraints
def _needs_exact(g):
    return None if g["dividend"] % g["divisor"] == 0 else f"{g['dividend']} does not divide exactly by {g['divisor']}; choose givens with no remainder or use a remainder template"


def _needs_remainder(g):
    return None if g["dividend"] % g["divisor"] != 0 else f"{g['dividend']} divides exactly by {g['divisor']}; a remainder template needs a remainder"


def _dividend_big_enough(g):
    return None if g["dividend"] >= g["divisor"] else "the dividend must be at least the divisor"


def _both(*checks):
    return lambda g: next((problem for problem in (check(g) for check in checks) if problem), None)


def _first_bigger(g):
    return None if g["first"] > g["second"] else "the first amount must be larger than the second so nothing goes below zero"


def _sum_at_most_one(g):
    return None if g["first"] + g["second"] <= 1 else "the two fractions of one whole must add to at most 1"


def _round_place_fits(g):
    return None if g["number"] >= g["place"] else "the number must be at least as large as the place it is rounded to"


def _digit_nonzero(g):
    digit = calc.digit_at(g["number"], g["place"]).value
    return None if g["number"] >= g["place"] and digit != 0 else "the digit in that place must exist and not be zero"


def _digit_exists(g):
    return None if g["number"] >= g["place"] else "the number has no digit in that place"


# ----------------------------------------------------------------------------------------------- the kinds
def _divide(g, mode):
    if mode == "exact":
        return calc.divide_exact(g["dividend"], g["divisor"])
    return calc.divide_with_remainder(g["dividend"], g["divisor"])


KINDS: dict[str, Kind] = {
    "divide_two": Kind("integer", {"dividend": "dividend", "divisor": "divisor"}, {
        "divide_bare": Template("What is {dividend} divided by {divisor}?", False, _both(_dividend_big_enough, _needs_exact), "exact"),
        "divide_bare_remainder": Template("What is {dividend} divided by {divisor}? Give the quotient and the remainder.", False,
                                          _both(_dividend_big_enough, _needs_remainder), "remainder"),
        "divide_share": Template("A shop shares {dividend} pencils equally among {divisor} boxes. How many pencils go in each box?",
                                 True, _both(_dividend_big_enough, _needs_exact), "exact"),
        "divide_packs": Template("A shop packs {dividend} pencils into boxes of {divisor}. How many full boxes can it make, "
                                 "and how many pencils are left over?", True, _both(_dividend_big_enough, _needs_remainder), "remainder")},
        _divide),
    "fraction_add": Kind("fraction", {"first": "fraction", "second": "fraction"}, {
        "fraction_add_bare": Template("What is {first} plus {second}?"),
        "fraction_add_pizza": Template("Maya ate {first} of a pizza. Sam ate {second} of the same pizza. How much of the pizza "
                                       "did they eat altogether?", True, _sum_at_most_one)},
        lambda g, m: calc.fraction_op("add", g["first"], g["second"])),
    "fraction_subtract": Kind("fraction", {"first": "fraction", "second": "fraction"}, {
        "fraction_subtract_bare": Template("What is {first} minus {second}?", False, _first_bigger),
        "fraction_subtract_juice": Template("A jug holds {first} of a litre of juice. Sam drinks {second} of a litre. "
                                            "How much of a litre is left?", True, _first_bigger)},
        lambda g, m: calc.fraction_op("subtract", g["first"], g["second"])),
    "fraction_multiply": Kind("fraction", {"whole": "whole", "fraction": "fraction"}, {
        "fraction_multiply_bare": Template("What is {whole} times {fraction}?"),
        "fraction_multiply_bags": Template("Each bag holds {fraction} of a kilogram of rice. How many kilograms of rice are in "
                                           "{whole} bags?", True)},
        lambda g, m: calc.fraction_op("multiply", g["whole"], g["fraction"])),
    "decimal_add": Kind("decimal", {"first": "decimal", "second": "decimal"}, {
        "decimal_add_bare": Template("What is {first} plus {second}?"),
        "decimal_add_ribbon": Template("A red ribbon is {first} metres long and a blue ribbon is {second} metres long. "
                                       "How many metres of ribbon are there altogether?", True)},
        lambda g, m: calc.decimal_op("add", g["first"], g["second"])),
    "decimal_subtract": Kind("decimal", {"first": "decimal", "second": "decimal"}, {
        "decimal_subtract_bare": Template("What is {first} minus {second}?", False, _first_bigger),
        "decimal_subtract_rope": Template("A rope is {first} metres long. Sam cuts off {second} metres. How many metres are left?",
                                          True, _first_bigger)},
        lambda g, m: calc.decimal_op("subtract", g["first"], g["second"])),
    "decimal_multiply": Kind("decimal", {"decimal": "decimal", "whole": "whole"}, {
        "decimal_multiply_bare": Template("What is {decimal} times {whole}?"),
        "decimal_multiply_planks": Template("One plank is {decimal} metres long. How long are {whole} planks laid end to end, "
                                            "in metres?", True)},
        lambda g, m: calc.decimal_op("multiply", g["decimal"], g["whole"])),
    "money_add": Kind("money", {"first": "money", "second": "money"}, {
        "money_add_bare": Template("What is {first} plus {second}?"),
        "money_add_shop": Template("A pencil costs {first} and an eraser costs {second}. How much do they cost altogether?", True)},
        lambda g, m: calc.money_op("add", g["first"], g["second"])),
    "money_subtract": Kind("money", {"first": "money", "second": "money"}, {
        "money_subtract_bare": Template("What is {first} minus {second}?", False, _first_bigger),
        "money_subtract_spend": Template("Sam has {first} and spends {second}. How much money does Sam have left?", True, _first_bigger)},
        lambda g, m: calc.money_op("subtract", g["first"], g["second"])),
    "money_multiply": Kind("money", {"price": "money", "count": "whole"}, {
        "money_multiply_bare": Template("What is {price} times {count}?"),
        "money_multiply_notebooks": Template("One notebook costs {price}. How much do {count} notebooks cost?", True)},
        lambda g, m: calc.money_op("multiply", g["price"], g["count"])),
    "compare_numbers": Kind("rule", {"left": "number", "right": "number"}, {
        "compare_bare": Template("Write <, > or = to make this true: {left} ___ {right}"),
        "compare_scores": Template("Sam scored {left} points and Ana scored {right} points. Write <, > or = to compare the "
                                   "scores: {left} ___ {right}", True)},
        lambda g, m: calc.compare(g["left"], g["right"])),
    "round_whole": Kind("rule", {"number": "dividend", "place": "place"}, {
        "round_bare": Template("Round {number} to the nearest {place_unit}.", False, _round_place_fits),
        "round_fans": Template("A stadium holds {number} fans. About how many fans is that, rounded to the nearest {place_unit}?",
                               True, _round_place_fits)},
        lambda g, m: calc.round_to_place(g["number"], g["place"])),
    "round_decimal": Kind("rule", {"number": "decimal", "places": "places"}, {
        "round_decimal_bare": Template("Round {number} to the nearest {unit}."),
        "round_decimal_runner": Template("A runner took {number} seconds. Round that time to the nearest {unit}.", True)},
        lambda g, m: calc.round_decimal(g["number"], g["places"])),
    "place_value_digit": Kind("rule", {"number": "dividend", "place": "place"}, {
        "place_value_of_digit": Template("What is the value of the digit in the {place_name} place of {number}?", False, _digit_nonzero, "value"),
        "place_digit": Template("Which digit is in the {place_name} place of {number}?", False, _digit_exists, "digit"),
        "place_value_story": Template("A school has {number} books. What is the value of the digit in the {place_name} place?",
                                      True, _digit_nonzero, "value")},
        lambda g, m: calc.digit_value(g["number"], g["place"]) if m == "value" else calc.digit_at(g["number"], g["place"])),
}


def _integer_kind(name: str, compute) -> Kind:
    templates = {template: Template(text, template in task_contract.SITUATION_TEMPLATES[name])
                 for template, text in task_contract.TEMPLATES[name].items()}
    return Kind("integer", {role: "nonneg" if "count" not in role else "count" for role in task_contract.ROLES[name]}, templates, compute)


# Add/subtract/groups are typed kinds too, so easy and medium use one short shape for every lesson. The wording, the rules (a
# difference cannot go below zero, group counts are positive ...) come from the original renderer, so they are identical; the
# answer comes from the calculator and must equal the renderer's own formula.
KINDS["add_two"] = _integer_kind("add_two", lambda g, m: calc.add(g["left_addend"], g["right_addend"]))
KINDS["subtract_two"] = _integer_kind("subtract_two", lambda g, m: calc.subtract(g["minuend"], g["subtrahend"]))
KINDS["equal_groups"] = _integer_kind("equal_groups", lambda g, m: calc.multiply(g["group_count"], g["group_size"]))
KINDS["two_equal_group_sets"] = _integer_kind(
    "two_equal_group_sets", lambda g, m: calc.multiply(calc.add(g["first_group_count"], g["second_group_count"]).value, g["group_size"]))
_ORIGINAL_RENDERER_KINDS = ("add_two", "subtract_two", "equal_groups", "two_equal_group_sets")


def _render_integer(task: dict, spec: Kind) -> Rendered:
    answer, prompt, stimulus = task_contract.render_task(task)   # same wording and the same rules as before; raises ValueError
    givens = task["givens"]
    result = spec.compute(givens, "")
    if result.value != answer:
        raise ValueError(f"the calculator ({result.value}) and the task formula ({answer}) disagree")
    template = spec.templates[task["template"]]
    return Rendered(task["kind"], result, "integer", "number", prompt, None, stimulus, template.situation, "integer", dict(givens), task["template"])


def _answer_shape(kind: str, result: calc.Calculation) -> tuple[str, str, list | None]:
    """(answer_type, response_type, accepted spellings or None for plain whole numbers)."""
    value = result.value
    if isinstance(value, dict):
        if value["remainder"] == 0:
            return "integer", "number", None
        q, r = value["quotient"], value["remainder"]
        return "remainder", "short_text", [f"{q} remainder {r}", f"{q} r {r}", f"{q} R {r}", f"{q}r{r}", f"{q} r{r}", f"{q} R{r}"]
    if isinstance(value, Fraction):
        return "fraction", "short_text", calc.fraction_answer_forms(value)
    if isinstance(value, Decimal):
        if kind.startswith("money"):
            return "money", "number", calc.money_answer_forms(value)
        forms = [calc.format_decimal(value)]
        two = format(value.quantize(Decimal("0.01")), "f") if value == value.quantize(Decimal("0.01")) else None
        if two and two not in forms:
            forms.append(two)
        return "decimal", "number", forms
    if isinstance(value, str):
        return "symbol", "short_text", calc.symbol_answer_forms(value)
    return "integer", "number", None


def render(task: Any) -> Rendered:
    if not isinstance(task, dict) or set(task) != ENVELOPE:
        raise ValueError("task requires exactly version, kind, givens, milestones, template and final_part_id")
    if task["version"] != VERSION:
        raise ValueError(f"unsupported task version; expected {VERSION}")
    kind = task["kind"]
    if not isinstance(kind, str) or kind not in KINDS:
        raise ValueError("unsupported task kind")
    spec = KINDS[kind]
    if task["milestones"] != []:
        raise ValueError(f"task milestones must be [] for {kind}")
    if task["final_part_id"] is not None:
        raise ValueError("number task final_part_id must be null")
    givens = task["givens"]
    if not isinstance(givens, dict) or set(givens) != set(spec.roles):
        raise ValueError(f"task givens for {kind} require exactly {tuple(spec.roles)}")
    template_name = task["template"]
    if not isinstance(template_name, str) or template_name not in spec.templates:
        raise ValueError(f"task template is not allowed for {kind}")
    if kind in _ORIGINAL_RENDERER_KINDS:
        return _render_integer(task, spec)
    template = spec.templates[template_name]
    parsed = {role: _PARSERS[given_type](givens[role], role) for role, given_type in spec.roles.items()}
    if template.check:
        problem = template.check(parsed)
        if problem:
            raise ValueError(f"{kind}/{template_name}: {problem}")
    shown = {role: _show(spec.roles[role] if spec.roles[role] in ("fraction", "decimal", "money") else "", value)
             for role, value in parsed.items()}
    if "place" in parsed:
        shown["place_name"] = calc.place_name(parsed["place"])
        shown["place_unit"] = _PLACE_UNIT[shown["place_name"]]
    if "places" in parsed:
        shown["unit"] = _UNIT[parsed["places"]]
    try:
        result = spec.compute(parsed, template.mode)
    except CalculatorError as exc:
        raise ValueError(f"{kind}: {exc}") from None
    answer_type, response_type, accept = _answer_shape(kind, result)
    prompt = template.text.format(**shown)
    stimulus = {"kind": "task_quantities", "givens": [{"role": role, "value": shown[role]} for role in spec.roles], "milestones": []}
    return Rendered(kind, result, answer_type, response_type, prompt, accept, stimulus, template.situation, spec.domain, parsed, template_name)


def validate(task: Any, allowed_kinds: tuple, difficulty: str, card_label: str = "this card") -> Rendered:
    rendered = render(task)
    if task["kind"] not in allowed_kinds:
        raise ValueError(f"task kind {task['kind']!r} is not allowed for card {card_label} (its teaching allows: {list(allowed_kinds)})")
    if difficulty == "hard":
        raise ValueError(f"hard questions are not built for task kind {task['kind']!r}; hard uses connected integer answer parts")
    if difficulty == "medium" and not rendered.situation:
        raise ValueError(f"medium needs a situation template for {task['kind']}, not the bare {task['template']!r}")
    return rendered


_ROLE_TEXT = {
    "dividend": "whole number, 1 or more", "divisor": "whole number, 2 or more", "whole": "whole number, 2 or more",
    "count": "whole number, 1 or more", "nonneg": "whole number, 0 or more", "fraction": "string such as '3/4' (positive, with a slash)",
    "decimal": "string with a point, such as '2.5'", "money": "string such as '$3.50' (at most two decimal places)",
    "number": "whole number, or string such as '0.5', '3/4' or '$4.10'",
    "place": "1, 10, 100, 1000, 10000, 100000 or 1000000", "places": "0, 1 or 2"}


def describe(name: str) -> dict:
    """What a model needs to choose this kind, kept short: the value type of each given, the template wording, and which
    templates are stories (medium needs a story). The type descriptions live once in value_types, not once per kind."""
    kind = KINDS[name]
    return {"givens": dict(kind.roles),
            "templates": {template_name: template.text for template_name, template in kind.templates.items()},
            "story": [template_name for template_name, template in kind.templates.items() if template.situation]}


def value_types(kind_names) -> dict:
    """The legend for the value types the given kinds use."""
    used = {given_type for name in kind_names for given_type in KINDS[name].roles.values()}
    return {given_type: _ROLE_TEXT[given_type] for given_type in sorted(used)}
