"""Exact arithmetic for question answers. No model calls, no floats.

Every function returns a ``Calculation`` that records the value, how it was displayed, the method, and the two engines
that agreed on it: Python's exact types (``int``, ``Fraction``, ``Decimal``, ``divmod``) and ``sympy``. If the two ever
disagree the calculator raises instead of returning, so a caller cannot get a quietly wrong answer.

A model's claimed answer is only ever *compared* with these results (``verify_claim``); it is never the source of one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from fractions import Fraction
from typing import Any

import sympy

ENGINES = ("python", "sympy")
_PLACES = {1: "ones", 10: "tens", 100: "hundreds", 1000: "thousands", 10000: "ten thousands",
           100000: "hundred thousands", 1000000: "millions"}
_PLACE_BY_NAME = {name: value for value, name in _PLACES.items()}


class CalculatorError(ValueError):
    """The inputs are not something the calculator can answer exactly."""


@dataclass(frozen=True)
class Calculation:
    value: Any          # int, Fraction, Decimal, str (a symbol) or dict (quotient/remainder), list (expanded form)
    display: str        # the canonical text of the answer
    method: str         # what was computed and how
    engines: tuple      # the engines that agreed


# ------------------------------------------------------------------------------------------------------- parsing
def _whole(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CalculatorError(f"expected a whole number, got {value!r}")
    return value


def parse_decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise CalculatorError("floats are never accepted; give a string such as '0.1'")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str) and re.fullmatch(r"\s*-?\d+(?:\.\d+)?\s*", value):
        return Decimal(value.strip())
    raise CalculatorError(f"not a decimal number: {value!r}")


def parse_money(value: Any) -> Decimal:
    if isinstance(value, str):
        value = value.strip().lstrip("$").replace(",", "")
    amount = parse_decimal(value)
    if amount != amount.quantize(Decimal("0.01")):
        raise CalculatorError(f"money has at most two decimal places: {value!r}")
    return amount.quantize(Decimal("0.01"))


def parse_fraction(value: Any) -> Fraction:
    if isinstance(value, bool) or isinstance(value, float):
        raise CalculatorError("floats are never accepted")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if not isinstance(value, str):
        raise CalculatorError(f"not a fraction: {value!r}")
    text = value.strip()
    mixed = re.fullmatch(r"(-?\d+)\s+(\d+)/(\d+)", text)
    simple = re.fullmatch(r"(-?\d+)/(\d+)", text)
    whole = re.fullmatch(r"-?\d+", text)
    try:
        if mixed:
            whole_part, num, den = int(mixed.group(1)), int(mixed.group(2)), int(mixed.group(3))
            if den == 0:
                raise ZeroDivisionError
            sign = -1 if whole_part < 0 else 1
            return Fraction(whole_part) + sign * Fraction(num, den)
        if simple:
            return Fraction(int(simple.group(1)), int(simple.group(2)))
        if whole:
            return Fraction(int(text))
    except ZeroDivisionError:
        raise CalculatorError(f"zero denominator: {value!r}") from None
    raise CalculatorError(f"not a fraction: {value!r}")


def _exact(value: Any) -> Fraction:
    """Any supported number as an exact Fraction (used for mixed-kind comparison)."""
    if isinstance(value, Decimal):
        return Fraction(value)
    if isinstance(value, (int, Fraction)) and not isinstance(value, bool):
        return Fraction(value)
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("$"):
            return Fraction(parse_money(text))
        if "/" in text:
            return parse_fraction(text)
        return Fraction(parse_decimal(text))
    raise CalculatorError(f"not a comparable number: {value!r}")


def _sympy_rational(value: Fraction) -> sympy.Rational:
    return sympy.Rational(value.numerator, value.denominator)


def _agree(python_value: Fraction, sympy_value: Any, what: str) -> None:
    if sympy.Rational(sympy_value) != _sympy_rational(Fraction(python_value)):
        raise CalculatorError(f"engines disagree on {what}: python {python_value}, sympy {sympy_value}")


# -------------------------------------------------------------------------------------------- whole numbers
def _whole_op(name: str, a: Any, b: Any) -> Calculation:
    a, b = _whole(a), _whole(b)
    if name == "add":
        value, via = a + b, sympy.Add(a, b)
    elif name == "subtract":
        value, via = a - b, sympy.Add(a, sympy.Mul(-1, b))
    else:
        value, via = a * b, sympy.Mul(a, b)
    if int(via) != value:
        raise CalculatorError(f"engines disagree on {name}({a}, {b})")
    return Calculation(value, str(value), f"{name} {a} and {b} (exact whole-number arithmetic)", ENGINES)


def add(a: Any, b: Any) -> Calculation:
    return _whole_op("add", a, b)


def subtract(a: Any, b: Any) -> Calculation:
    return _whole_op("subtract", a, b)


def multiply(a: Any, b: Any) -> Calculation:
    return _whole_op("multiply", a, b)


def divide_with_remainder(dividend: Any, divisor: Any) -> Calculation:
    """Whole-number division with both parts checked: quotient * divisor + remainder == dividend, remainder < divisor."""
    dividend, divisor = _whole(dividend), _whole(divisor)
    if dividend < 0 or divisor <= 0:
        raise CalculatorError("division needs a nonnegative dividend and a positive divisor")
    quotient, remainder = divmod(dividend, divisor)
    if (int(sympy.floor(sympy.Rational(dividend, divisor))) != quotient
            or int(sympy.Mod(dividend, divisor)) != remainder
            or quotient * divisor + remainder != dividend or not 0 <= remainder < divisor):
        raise CalculatorError(f"engines disagree on {dividend} divided by {divisor}")
    display = str(quotient) if remainder == 0 else f"{quotient} remainder {remainder}"
    return Calculation({"quotient": quotient, "remainder": remainder}, display,
                       f"divmod({dividend}, {divisor}); checked quotient x divisor + remainder = dividend", ENGINES)


def divide_exact(dividend: Any, divisor: Any) -> Calculation:
    result = divide_with_remainder(dividend, divisor)
    if result.value["remainder"] != 0:
        raise CalculatorError(f"{dividend} does not divide exactly by {divisor} (remainder {result.value['remainder']})")
    return Calculation(result.value["quotient"], str(result.value["quotient"]),
                       f"exact division {dividend} / {divisor} via divmod (remainder 0)", ENGINES)


# ------------------------------------------------------------------------------------------------- fractions
def format_fraction(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def format_mixed(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    whole, rest = divmod(abs(value.numerator), value.denominator)
    sign = "-" if value < 0 else ""
    if whole == 0:
        return f"{sign}{rest}/{value.denominator}"
    return f"{sign}{whole} {rest}/{value.denominator}"


def fraction_answer_forms(value: Fraction) -> list[str]:
    forms = [format_fraction(value)]
    mixed = format_mixed(value)
    if mixed not in forms:
        forms.append(mixed)
    return forms


def fraction_op(name: str, a: Any, b: Any) -> Calculation:
    x, y = parse_fraction(a), parse_fraction(b)
    sx, sy = _sympy_rational(x), _sympy_rational(y)
    if name == "add":
        value, via = x + y, sx + sy
    elif name == "subtract":
        value, via = x - y, sx - sy
    elif name == "multiply":
        value, via = x * y, sx * sy
    elif name == "divide":
        if y == 0:
            raise CalculatorError("division by a zero fraction")
        value, via = x / y, sx / sy
    else:
        raise CalculatorError(f"unknown fraction operation {name!r}")
    _agree(value, via, f"{name} {a} {b}")
    return Calculation(value, format_fraction(value), f"{name} fractions {format_fraction(x)} and {format_fraction(y)}, simplified (exact Fraction)", ENGINES)


# ---------------------------------------------------------------------------------------- decimals and money
def format_decimal(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def format_money(value: Decimal) -> str:
    return "$" + format(value.quantize(Decimal("0.01")), "f")


def _decimal_op(name: str, x: Decimal, y: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 60
        value = {"add": x + y, "subtract": x - y, "multiply": x * y}[name]
    via = {"add": _sympy_rational(Fraction(x)) + _sympy_rational(Fraction(y)),
           "subtract": _sympy_rational(Fraction(x)) - _sympy_rational(Fraction(y)),
           "multiply": _sympy_rational(Fraction(x)) * _sympy_rational(Fraction(y))}[name]
    _agree(Fraction(value), via, f"{name} {x} {y}")
    return value


def decimal_op(name: str, a: Any, b: Any) -> Calculation:
    if name not in ("add", "subtract", "multiply"):
        raise CalculatorError(f"unknown decimal operation {name!r}")
    x, y = parse_decimal(a), parse_decimal(b)
    value = _decimal_op(name, x, y)
    return Calculation(value, format_decimal(value), f"{name} decimals {format_decimal(x)} and {format_decimal(y)} (exact Decimal)", ENGINES)


def money_op(name: str, a: Any, b: Any) -> Calculation:
    if name not in ("add", "subtract", "multiply"):
        raise CalculatorError(f"unknown money operation {name!r}")
    x = parse_money(a)
    y = parse_decimal(b) if name == "multiply" else parse_money(b)  # money x a plain count
    if name == "multiply" and y != y.to_integral_value():
        raise CalculatorError("money can be multiplied by a whole number of items only")
    value = _decimal_op(name, x, y)
    if value != value.quantize(Decimal("0.01")):
        raise CalculatorError("money result has more than two decimal places")
    value = value.quantize(Decimal("0.01"))
    return Calculation(value, format_money(value), f"{name} money {format_money(x)} and {format_decimal(y)} (exact Decimal, two places)", ENGINES)


def money_answer_forms(value: Decimal) -> list[str]:
    value = value.quantize(Decimal("0.01"))
    plain = format(value, "f")
    forms = [format_money(value), plain]
    short = plain.rstrip("0").rstrip(".") if "." in plain else plain
    if short not in forms:
        forms.append(short)
    return forms


# --------------------------------------------------------------------------------------------------- rounding
def _power_of_ten(place: Any) -> int:
    place = _whole(place)
    if place < 1 or set(str(place)[1:]) - {"0"} or str(place)[0] != "1":
        raise CalculatorError(f"place must be 1, 10, 100, 1000 ...: {place!r}")
    return place


def round_to_place(number: Any, place: Any) -> Calculation:
    """Round a whole number to the nearest 10, 100, 1000 ... with halves rounding up (the school rule)."""
    number, place = _whole(number), _power_of_ten(place)
    if number < 0:
        raise CalculatorError("rounding is defined for nonnegative whole numbers here")
    value = (number + place // 2) // place * place
    via = int(sympy.floor(sympy.Rational(number, place) + sympy.Rational(1, 2))) * place
    if value != via:
        raise CalculatorError("engines disagree on rounding")
    return Calculation(value, str(value), f"round {number} to the nearest {_PLACES.get(place, place)} (halves round up)", ENGINES)


def round_decimal(number: Any, places: int) -> Calculation:
    if isinstance(places, bool) or not isinstance(places, int) or places < 0:
        raise CalculatorError("decimal places must be a nonnegative whole number")
    x = parse_decimal(number)
    value = x.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    scale = sympy.Integer(10) ** places
    via = sympy.floor(_sympy_rational(Fraction(x)) * scale + sympy.Rational(1, 2)) / scale
    _agree(Fraction(value), via, "decimal rounding")
    return Calculation(value, format_decimal(value), f"round {format_decimal(x)} to {places} decimal place(s) (halves round up)", ENGINES)


# ------------------------------------------------------------------------------------------------ comparison
_SYMBOL_WORDS = {"<": ["<", "less than"], ">": [">", "greater than", "more than"], "=": ["=", "equal to", "equals", "the same"]}


def compare(a: Any, b: Any) -> Calculation:
    x, y = _exact(a), _exact(b)
    symbol = "<" if x < y else ">" if x > y else "="
    via = sympy.Rational(x.numerator, x.denominator) - sympy.Rational(y.numerator, y.denominator)
    if (symbol == "<") != bool(via < 0) or (symbol == ">") != bool(via > 0):
        raise CalculatorError("engines disagree on a comparison")
    return Calculation(symbol, symbol, f"compare {a} and {b} exactly (as fractions of whole numbers)", ENGINES)


def symbol_answer_forms(symbol: str) -> list[str]:
    return list(_SYMBOL_WORDS[symbol])


# ----------------------------------------------------------------------------------------------- place value
def place_name(place: int) -> str:
    if place not in _PLACES:
        raise CalculatorError(f"no name for place value {place!r}")
    return _PLACES[place]


def place_value_of_name(name: str) -> int:
    if name not in _PLACE_BY_NAME:
        raise CalculatorError(f"unknown place name {name!r}")
    return _PLACE_BY_NAME[name]


def digit_at(number: Any, place: Any) -> Calculation:
    number, place = _whole(number), _power_of_ten(place)
    if number < 0:
        raise CalculatorError("place value is defined for nonnegative whole numbers here")
    digit = number // place % 10
    return Calculation(digit, str(digit), f"the digit of {number} in the {_PLACES.get(place, place)} place", ENGINES)


def digit_value(number: Any, place: Any) -> Calculation:
    digit = digit_at(number, place).value
    value = digit * place
    if int(sympy.Integer(digit) * place) != value:
        raise CalculatorError("engines disagree on place value")
    return Calculation(value, str(value), f"the value of the digit {digit} in the {_PLACES.get(place, place)} place of {number}", ENGINES)


def expanded_form(number: Any) -> Calculation:
    number = _whole(number)
    if number < 0:
        raise CalculatorError("expanded form is defined for nonnegative whole numbers here")
    parts = [int(digit) * 10 ** index for index, digit in enumerate(reversed(str(number))) if digit != "0"] or [0]
    parts.reverse()
    if int(sympy.Add(*parts)) != number:
        raise CalculatorError("engines disagree on expanded form")
    return Calculation(parts, " + ".join(map(str, parts)), f"expanded form of {number}", ENGINES)


# ----------------------------------------------------------------------------------------- verifying a claim
def _claim_matches(result: Calculation, claim: Any) -> bool:
    value = result.value
    try:
        if isinstance(value, dict):  # quotient and remainder
            if isinstance(claim, int) and not isinstance(claim, bool):
                return value["remainder"] == 0 and claim == value["quotient"]
            text = str(claim).strip().lower()
            pair = re.fullmatch(r"(\d+)\s*(?:r|rem|remainder)\s*(\d+)", text)
            if pair:
                return (int(pair.group(1)), int(pair.group(2))) == (value["quotient"], value["remainder"])
            return value["remainder"] == 0 and re.fullmatch(r"\d+", text) is not None and int(text) == value["quotient"]
        if isinstance(value, str):  # a comparison symbol
            return str(claim).strip().lower() in [form.lower() for form in _SYMBOL_WORDS[value]]
        if isinstance(value, list):
            return list(claim) == value
        if isinstance(value, Fraction):
            return parse_fraction(str(claim).strip()) == value
        if isinstance(value, Decimal):
            text = str(claim).strip()
            return Fraction(parse_money(text) if text.startswith("$") else parse_decimal(text)) == Fraction(value)
        if isinstance(value, int):
            if isinstance(claim, bool):
                return False
            text = str(claim).strip().replace(",", "")
            return re.fullmatch(r"-?\d+", text) is not None and int(text) == value
    except (CalculatorError, ValueError, InvalidOperation, TypeError):
        return False
    return False


def verify_claim(result: Calculation, claim: Any) -> dict[str, Any]:
    """Compare a claimed answer (for example the model's) with the computed one. The claim is never the source."""
    return {"method": result.method, "computed": result.display, "engines": list(result.engines),
            "claimed": None if claim is None else str(claim), "matches": _claim_matches(result, claim)}
