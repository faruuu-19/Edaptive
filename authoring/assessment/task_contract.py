"""Bounded maths inputs and deterministic wording for the two reviewed cards."""

from __future__ import annotations

import re
from typing import Any

VERSION = "bounded-maths-task-v1"
# Which task shapes a lesson's taught operations make available. This is a rule about shapes, not a list of cards: the
# operations, the number domain and the rules come from each card's own teaching (lesson_profile.py).
SUPPORTED_OPERATIONS = ("add", "subtract", "multiply", "divide")
# Kinds that can also be a hard (connected multi-part) question: the integer ones, whose parts the evaluator can chain.
HARD_KINDS = ("add_two", "subtract_two", "equal_groups", "two_equal_group_sets", "divide_two")
# The operations each task kind verifies, used to compare a question's wording with what was actually computed.
KIND_OPERATIONS = {
    "add_two": ("add",), "subtract_two": ("subtract",), "equal_groups": ("multiply",), "two_equal_group_sets": ("multiply", "add"),
    "divide_two": ("divide",), "fraction_add": ("add",), "fraction_subtract": ("subtract",), "fraction_multiply": ("multiply",),
    "decimal_add": ("add",), "decimal_subtract": ("subtract",), "decimal_multiply": ("multiply",), "money_add": ("add",),
    "money_subtract": ("subtract",), "money_multiply": ("multiply",), "compare_numbers": (), "round_whole": (), "round_decimal": (),
    "place_value_digit": ()}
_TYPED_PREFIX = {"fraction": "fraction", "decimal": "decimal", "money": "money"}
_TYPED_OPERATIONS = ("add", "subtract", "multiply")


def kinds_for_operations(operations, domain: str = "integer", repeated_addition: bool = False) -> tuple[str, ...]:
    """Task kinds a lesson may use, given the operations it teaches and the kind of number it works with.

    In a whole-number multiplication lesson plain addition questions are not offered (addition lives inside the group
    shapes) unless the lesson itself teaches repeated addition. Fraction, decimal and money lessons get typed kinds.
    Empty means no contract applies.
    """
    taught = set(operations) & set(SUPPORTED_OPERATIONS)
    if domain in _TYPED_PREFIX:
        return tuple(f"{_TYPED_PREFIX[domain]}_{name}" for name in _TYPED_OPERATIONS if name in taught)
    kinds = []
    if "add" in taught and ("multiply" not in taught or repeated_addition):
        kinds.append("add_two")
    if "subtract" in taught:
        kinds.append("subtract_two")
    if "multiply" in taught:
        kinds.append("equal_groups")
    if {"add", "multiply"} <= taught:
        kinds.append("two_equal_group_sets")
    if "divide" in taught:
        kinds.append("divide_two")
    return tuple(kinds)


def kinds_for_rules(rules, domain: str = "integer") -> tuple[str, ...]:
    """Rule-checkable kinds (comparison, rounding, place value) for the rules a lesson teaches."""
    kinds = []
    if "compare" in rules:
        kinds.append("compare_numbers")
    if "round" in rules:
        kinds.append("round_whole" if domain == "integer" else "round_decimal" if domain in ("decimal", "money") else None)
    if "place_value" in rules and domain == "integer":
        kinds.append("place_value_digit")
    return tuple(kind for kind in kinds if kind)


ROLES = {
    "divide_two": ("dividend", "divisor"),
    "add_two": ("left_addend", "right_addend"),
    "subtract_two": ("minuend", "subtrahend"),
    "equal_groups": ("group_count", "group_size"),
    "two_equal_group_sets": ("first_group_count", "second_group_count", "group_size"),
}
TEMPLATES = {
    "divide_two": {
        "divide_hard_packs": "A shop packs {dividend} pencils into boxes of {divisor}. How many full boxes can it make, and how many pencils are left over?",
    },
    "add_two": {
        "add_bare": "What is {left_addend} plus {right_addend}?",
        "add_shop_gains": "A shop has {left_addend} pencils and receives {right_addend} more pencils. How many pencils does it have now?",
    },
    "subtract_two": {
        "subtract_bare": "What is {minuend} minus {subtrahend}?",
        "subtract_shop_sells": "A shop has {minuend} pencils and sells {subtrahend} pencils. How many pencils are left?",
    },
    "equal_groups": {
        "groups_bare": "What is {group_count} times {group_size}?",
        "groups_boxes": "There are {group_count} boxes with {group_size} pencils in each box. How many pencils are there altogether?",
    },
    "two_equal_group_sets": {
        "groups_two_shelves": "One shelf has {first_group_count} trays with {group_size} pencils in each tray. Another shelf has {second_group_count} trays with {group_size} pencils in each tray. How many pencils are there altogether?",
    },
}
SITUATION_TEMPLATES = {
    "divide_two": frozenset({"divide_hard_packs"}),
    "add_two": frozenset({"add_shop_gains"}),
    "subtract_two": frozenset({"subtract_shop_sells"}),
    "equal_groups": frozenset({"groups_boxes"}),
    "two_equal_group_sets": frozenset({"groups_two_shelves"}),
}
_ID = re.compile(r"[a-z][a-z_]*\Z")


def is_situation_task(task: dict[str, Any] | None) -> bool:
    """Classify an already validated task by its approved role-bearing template."""
    return task is not None and task["template"] in SITUATION_TEMPLATES.get(task["kind"], ())


def render_task(task: Any) -> tuple[int, str, dict[str, Any]]:
    """Validate the four shapes and derive the answer and text without working ASTs.

    Card mapping is a separate gate in validate_task, including for subtract_two,
    which has a defined renderer but is not mapped to either current card.
    """
    if not isinstance(task, dict) or set(task) != {
        "version", "kind", "givens", "milestones", "template", "final_part_id"
    }:
        raise ValueError("task requires exactly version, kind, givens, milestones, template and final_part_id")
    if task["version"] != VERSION:
        raise ValueError(f"unsupported task version; expected {VERSION}")
    kind = task["kind"]
    if not isinstance(kind, str) or kind not in ROLES:
        raise ValueError("unsupported task kind")
    givens = task["givens"]
    if not isinstance(givens, dict) or set(givens) != set(ROLES[kind]):
        raise ValueError(f"task givens for {kind} require exactly {ROLES[kind]}")
    if any(type(value) is not int or value < 0 for value in givens.values()):
        raise ValueError("task givens must be nonnegative integer values (not booleans)")
    if any(givens[role] < 1 for role in ROLES[kind] if "count" in role):
        raise ValueError("task group counts must be positive integers")
    if kind == "divide_two" and (givens["divisor"] < 2 or givens["dividend"] < givens["divisor"]):
        raise ValueError("task divisor must be at least 2 and the dividend at least the divisor")
    if kind == "subtract_two" and givens["minuend"] < givens["subtrahend"]:
        raise ValueError("task minuend must be at least the subtrahend; subtraction roles cannot be swapped")
    template = task["template"]
    if not isinstance(template, str) or template not in TEMPLATES[kind]:
        raise ValueError(f"task template is not allowed for {kind}")
    final = task["final_part_id"]
    if final is not None and (not isinstance(final, str) or not _ID.fullmatch(final)):
        raise ValueError("task final_part_id must be a lowercase letter/underscore part ID or null")
    milestones = task["milestones"]
    if not isinstance(milestones, list) or (kind != "add_two" and milestones):
        raise ValueError("task milestones must be an array; only add_two supports next_hundred milestones")
    ids: set[str] = set(givens)
    sources: set[str] = set()
    for milestone in milestones:
        if not isinstance(milestone, dict) or set(milestone) != {"id", "kind", "of_given", "value"}:
            raise ValueError("task milestone requires exactly id, kind, of_given and value")
        milestone_id, source = milestone["id"], milestone["of_given"]
        if not isinstance(milestone_id, str) or not _ID.fullmatch(milestone_id) or milestone_id in ids:
            raise ValueError("task milestone needs a unique lowercase letter/underscore ID")
        if milestone["kind"] != "next_hundred" or not isinstance(source, str) or source not in givens or source in sources:
            raise ValueError("task milestone must be next_hundred for a unique original given")
        if type(milestone["value"]) is not int or milestone["value"] != (givens[source] // 100 + 1) * 100:
            raise ValueError("task milestone value must be the next strictly greater hundred after its given")
        ids.add(milestone_id)
        sources.add(source)
    if kind == "add_two":
        answer = givens["left_addend"] + givens["right_addend"]
    elif kind == "subtract_two":
        answer = givens["minuend"] - givens["subtrahend"]
    elif kind == "divide_two":
        answer = givens["dividend"] // givens["divisor"]
    elif kind == "equal_groups":
        answer = givens["group_count"] * givens["group_size"]
    else:
        answer = (givens["first_group_count"] + givens["second_group_count"]) * givens["group_size"]
    prompt = TEMPLATES[kind][template].format(**givens)
    if template == "groups_boxes" and givens["group_count"] == 1:
        prompt = prompt.replace("There are 1 boxes", "There is 1 box")
    if template == "groups_two_shelves":
        prompt = prompt.replace("has 1 trays", "has 1 tray")
    if template in ("groups_boxes", "groups_two_shelves") and givens["group_size"] == 1:
        prompt = prompt.replace("1 pencils", "1 pencil")
    stimulus = {
        "kind": "task_quantities",
        "givens": [{"role": role, "value": givens[role]} for role in ROLES[kind]],
        "milestones": [dict(milestone) for milestone in milestones],
    }
    return answer, prompt, stimulus


def validate_task(task: Any, allowed_kinds: tuple[str, ...], difficulty: str, card_label: str = "this card") -> tuple[int, str, dict[str, Any]]:
    rendered = render_task(task)
    if task["kind"] not in allowed_kinds:
        raise ValueError(f"task kind {task['kind']!r} is not allowed for card {card_label} (its teaching allows: {list(allowed_kinds)})")
    if difficulty != "hard" and task["final_part_id"] is not None:
        raise ValueError("number task final_part_id must be null")
    if difficulty == "hard" and task["final_part_id"] is None:
        raise ValueError("hard task requires a final_part_id")
    return rendered


def render_part_instruction(instruction: Any, expression: Any, prior_labels: dict[str, str]) -> str:
    """Render an already safely evaluated expression; never interpret model prose."""
    if instruction != {"kind": "calculate"}:
        raise ValueError("answer part instruction must be exactly {kind: 'calculate'}")

    def render(node: Any) -> str:
        if type(node) is int:
            return str(node)
        if set(node) == {"ref"}:
            return f"your answer to part ({prior_labels[node['ref']]})"
        if "operands" in node:
            left, right = node["operands"]
            if node["operation"] == "quotient":
                return f"(the whole-number quotient of {render(left)} divided by {render(right)})"
            if node["operation"] == "remainder":
                return f"(the remainder when {render(left)} is divided by {render(right)})"
            word = {"add": "plus", "subtract": "minus", "multiply": "times", "divide": "divided by"}[node["operation"]]
            return f"({render(left)} {word} {render(right)})"
        return str(node.get("number", node.get("value")))

    return f"Calculate {render(expression)}."
