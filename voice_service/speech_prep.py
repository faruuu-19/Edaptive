"""Turn one script segment's text into what is spoken and what is only shown.

Pure Python, no model and no I/O, so it can move into the app unchanged. One call returns:

* ``utterances``: sentence-sized units, each with a ``caption`` (cleaned text, digits kept) and
  ``spoken`` (numbers and symbols written out as words), the unit the player streams and highlights;
* ``cues``: visual cues ("Look here", "[show: ...]") that the player shows as a small text caption and
  that are never read aloud;
* ``review_flags``: anything the code could not settle by rule (it never guesses silently).

Numbers are always read as quantities (math lessons), never as years or digit strings, except leading-zero
and very long digit strings, which are read digit by digit.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Tuple

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
         "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_SCALES = [(10 ** 12, "trillion"), (10 ** 9, "billion"), (10 ** 6, "million"), (10 ** 3, "thousand")]
_MAX_QUANTITY_DIGITS = 15

_ORDINAL_WORDS = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth",
                  "nine": "ninth", "twelve": "twelfth"}

_ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "rs", "st", "vs", "no", "e.g", "i.e", "etc", "approx"}

_UNITS = {"mm": ("millimeter", "millimeters"), "cm": ("centimeter", "centimeters"),
          "km": ("kilometer", "kilometers"), "m": ("meter", "meters"), "kg": ("kilogram", "kilograms"),
          "g": ("gram", "grams"), "ml": ("milliliter", "milliliters"), "L": ("liter", "liters")}


@dataclass(frozen=True)
class Utterance:
    caption: str
    spoken: str


@dataclass(frozen=True)
class PreparedSegment:
    utterances: Tuple[Utterance, ...]
    cues: Tuple[str, ...]
    review_flags: Tuple[str, ...]


# ---------------------------------------------------------------- numbers

def _below_thousand(n: int) -> str:
    words: List[str] = []
    if n >= 100:
        words.append(_ONES[n // 100] + " hundred")
        n %= 100
    if n >= 20:
        words.append(_TENS[n // 10] + ("-" + _ONES[n % 10] if n % 10 else ""))
    elif n > 0 or not words:
        words.append(_ONES[n])
    return " ".join(words)


def number_to_words(n: int) -> str:
    """Whole number as American English words, e.g. 574 -> 'five hundred seventy-four'."""
    if n < 0:
        return "negative " + number_to_words(-n)
    if n < 1000:
        return _below_thousand(n)
    parts: List[str] = []
    for value, name in _SCALES:
        if n >= value:
            parts.append(_below_thousand(n // value) + " " + name)
            n %= value
    if n:
        parts.append(_below_thousand(n))
    return " ".join(parts)


def _digits_to_words(digits: str) -> str:
    return " ".join(_ONES[int(d)] for d in digits)


def _quantity_words(digits: str) -> str:
    """A run of digits (commas already removed) as a quantity, or digit by digit when that is safer."""
    if (len(digits) > 1 and digits.startswith("0")) or len(digits) > _MAX_QUANTITY_DIGITS:
        return _digits_to_words(digits)
    return number_to_words(int(digits))


def _decimal_words(whole: str, frac: str) -> str:
    return _quantity_words(whole) + " point " + _digits_to_words(frac)


def _ordinal_words(n: int) -> str:
    words = number_to_words(n)
    head, sep, last = words.rpartition(" ")
    if "-" in last:
        a, b = last.rsplit("-", 1)
        return (head + sep if head else "") + a + "-" + _ordinal_last(b)
    return (head + sep if head else "") + _ordinal_last(last)


def _ordinal_last(word: str) -> str:
    if word in _ORDINAL_WORDS:
        return _ORDINAL_WORDS[word]
    if word.endswith("y"):
        return word[:-1] + "ieth"
    return word + "th"


def _fraction_words(num: int, den: int) -> str:
    plural = num != 1
    if den == 2:
        denominator = "halves" if plural else "half"
    else:
        denominator = _ordinal_words(den) + ("s" if plural else "")
    return number_to_words(num) + " " + denominator


# ---------------------------------------------------------------- caption cleaning

_EMOJI_KEEP = {"°"}


def _is_decoration(ch: str) -> bool:
    if ch in _EMOJI_KEEP:
        return False
    cp = ord(ch)
    if cp in (0x200D, 0xFE0E, 0xFE0F, 0x20E3):
        return True
    if 0x1F3FB <= cp <= 0x1F3FF or 0xE0020 <= cp <= 0xE007F or 0x1F1E6 <= cp <= 0x1F1FF:
        return True
    return unicodedata.category(ch) in ("So", "Cs", "Co") or (unicodedata.category(ch) == "Sk" and cp > 0x2000)


_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', " ": " "})
_BRACKET_CUE = re.compile(r"\[\s*(?:show\s*:\s*)?([^\]]*?)\s*\]", re.IGNORECASE)
_MARKDOWN_PAIR = re.compile(r"(\*{1,2})([^*\n]+?)\1")


def _clean_caption_text(text: str, flags: List[str], cues: List[str]) -> str:
    t = unicodedata.normalize("NFC", text).translate(_QUOTES)
    if "<CONTENT>" in t:
        t = t.replace("<CONTENT>", " ")
        flags.append("template_marker_removed")

    def take_cue(match: "re.Match[str]") -> str:
        cue = match.group(1).strip()
        if cue:
            cues.append(cue)
        return " "

    t = _BRACKET_CUE.sub(take_cue, t)
    t = _MARKDOWN_PAIR.sub(r"\2", t)
    t = re.sub(r"[`#]+", " ", t)
    t = "".join(" " if _is_decoration(ch) else ch for ch in t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([.,!?;:])", r"\1", t)
    return t


_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"(])|(?<=[.!?][\"')])\s+(?=[A-Z0-9\"(])")


def _split_sentences(text: str) -> List[str]:
    pieces = [p for p in _SPLIT.split(text) if p]
    merged: List[str] = []
    for piece in pieces:
        if merged:
            last_word = merged[-1].rstrip().split(" ")[-1].rstrip(".").lower()
            if merged[-1].endswith(".") and last_word in _ABBREVIATIONS:
                merged[-1] = merged[-1] + " " + piece
                continue
        merged.append(piece)
    return merged


# ---------------------------------------------------------------- visual cues

_NOT_PICTURE = r"(?!numbers?\s+\d|digits?\b|equation|problem|sum\b|question|words?\b)"
_CUE_WHOLE = [
    re.compile(r"^Look at (?:our|the|this|these|that|my) " + _NOT_PICTURE + r"[^.!?]*[.!?]+$", re.IGNORECASE),
    re.compile(r"^Here(?: is|'s) something (?:for you )?to look at[.!?]*$", re.IGNORECASE),
    re.compile(r"^(?:You can )?watch (?:me|this)\b[^.!?]*[.!?]+$", re.IGNORECASE),
]
_LOOK_HERE = re.compile(r"^Look here\s*[:,.!]*\s*(.*)$", re.IGNORECASE)
_POSSIBLE_VISUAL = re.compile(r"\b(look|looks|looking|watch|see|picture|show|shows|draw)\b", re.IGNORECASE)


def _split_cues(sentences: List[str], cues: List[str]) -> List[str]:
    kept: List[str] = []
    for sentence in sentences:
        m = _LOOK_HERE.match(sentence)
        if m:
            cues.append("Look here")
            rest = m.group(1).strip()
            if rest:
                kept.append(rest[0].upper() + rest[1:])
            continue
        if any(p.match(sentence) for p in _CUE_WHOLE):
            cues.append(sentence.rstrip(".!? "))
            continue
        kept.append(sentence)
    return kept


# ---------------------------------------------------------------- merging short sentences

def _merge_short(sentences: List[str], min_words: int) -> List[str]:
    merged: List[str] = []
    buffer = ""
    for sentence in sentences:
        buffer = (buffer + " " + sentence).strip() if buffer else sentence
        if len(buffer.split()) >= min_words:
            merged.append(buffer)
            buffer = ""
    if buffer:
        if merged:
            merged[-1] = merged[-1] + " " + buffer
        else:
            merged.append(buffer)
    return merged


# ---------------------------------------------------------------- speech conversion

_NUM = r"\d[\d,]*(?:\.\d+)?"


def _number_text(raw: str) -> str:
    raw = raw.replace(",", "")
    if "." in raw:
        whole, frac = raw.split(".", 1)
        return _decimal_words(whole, frac)
    return _quantity_words(raw)


def _money_dollars(m: "re.Match[str]") -> str:
    whole = m.group(1).replace(",", "")
    cents = m.group(2)
    words = _quantity_words(whole) + (" dollar" if whole == "1" else " dollars")
    if cents and cents != "00":
        words += " and " + number_to_words(int(cents)) + (" cent" if int(cents) == 1 else " cents")
    return " " + words + " "


def _rupees(m: "re.Match[str]") -> str:
    raw = m.group(1).replace(",", "")
    one = raw == "1"
    return " " + _number_text(raw) + (" rupee" if one else " rupees") + " "


def _unit_text(count_raw: str, unit_key: str, squared: bool) -> str:
    count = count_raw.replace(",", "")
    singular, plural = _UNITS[unit_key]
    noun = singular if count == "1" else plural
    if squared:
        noun = "square " + noun
    return " " + _number_text(count) + " " + noun + " "


def _speechify(sentence: str, index: int, flags: List[str]) -> str:
    t = sentence
    # degrees, money, percent, units
    t = re.sub(r"(?<=\d)\s?°\s?C\b", " degrees Celsius", t)
    t = re.sub(r"(?<=\d)\s?°\s?F\b", " degrees Fahrenheit", t)
    t = re.sub(r"(?<=\d)\s?°", " degrees", t)
    t = re.sub(r"\$\s?(\d[\d,]*)(?:\.(\d{2}))?", _money_dollars, t)
    t = re.sub(r"\bRs\.?\s?(" + _NUM + r")", _rupees, t)
    t = re.sub(r"(" + _NUM + r")\s?%", lambda m: " " + _number_text(m.group(1)) + " percent ", t)
    t = re.sub(r"(" + _NUM + r")\s?(mm|cm|km|m)\s?²", lambda m: _unit_text(m.group(1), m.group(2), True), t)
    t = re.sub(r"(" + _NUM + r")\s?(mm|cm|km|kg|ml|mL|m|g|L)\b(?!\w)",
               lambda m: _unit_text(m.group(1), "ml" if m.group(2) in ("ml", "mL") else m.group(2), False), t)
    # fractions (unspaced), ordinals, remainder
    t = re.sub(r"(?<![\d/.])(\d+)/(\d+)(?![\d/])",
               lambda m: " " + _fraction_words(int(m.group(1)), int(m.group(2))) + " "
               if int(m.group(2)) >= 2 else m.group(0), t)
    t = re.sub(r"\b(\d+)(?:st|nd|rd|th)\b", lambda m: " " + _ordinal_words(int(m.group(1))) + " ", t)
    t = re.sub(r"(?<=\d)\s?[Rr]\s?(?=\d)", " remainder ", t)
    # operators
    t = re.sub(r"\s*≠\s*", " does not equal ", t)
    t = re.sub(r"\s*≤\s*", " is less than or equal to ", t)
    t = re.sub(r"\s*≥\s*", " is greater than or equal to ", t)
    t = re.sub(r"\s*<\s*", " is less than ", t)
    t = re.sub(r"\s*>\s*", " is greater than ", t)
    t = re.sub(r"\s*=\s*", " equals ", t)
    t = re.sub(r"\s*\+\s*", " plus ", t)
    t = re.sub(r"\s*−\s*", " minus ", t)
    t = re.sub(r"(?<=[\d_?□])\s[-–]\s(?=[\d(_?□])", " minus ", t)
    t = re.sub(r"(?<=[\d_?□])\s?[x×]\s?(?=[\d_?□])", " times ", t)
    t = re.sub(r"(?<=\d)\s?\*\s?(?=\d)", " times ", t)
    t = re.sub(r"\s*÷\s*", " divided by ", t)
    t = re.sub(r"(?<=[\d_?□])\s/\s(?=[\d(_?□])", " divided by ", t)
    # blanks
    t = re.sub(r"_{2,}|□", " what number ", t)
    t = re.sub(r"(?<=\bplus )\?|(?<=\bminus )\?|(?<=\btimes )\?|(?<=\bequals )\?|(?<=\bdivided by )\?"
               r"|(?<=^)\?(?=\s+(?:plus|minus|times|equals|divided))", " what number ", t)
    t = re.sub(r"\?(?=\s+(?:plus|minus|times|equals|divided by|is less|is greater))", " what number ", t)
    # negative numbers, number ranges written with a bare hyphen
    t = re.sub(r"(?<![\w)])-(?=\d)", " negative ", t)
    if re.search(r"\d-\d", t):
        flags.append("ambiguous_number_hyphen:%d" % index)
        t = re.sub(r"(?<=\d)-(?=\d)", " to ", t)
    # remaining numerals
    t = re.sub(r"(?<![A-Za-z\d.])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![A-Za-z\d])",
               lambda m: " " + _number_text(m.group(0)) + " ", t)
    t = re.sub(r"(?<![A-Za-z\d.])\d+(?:\.\d+)?(?![A-Za-z\d])",
               lambda m: " " + _number_text(m.group(0)) + " ", t)
    # punctuation that is not spoken
    t = re.sub(r"[–—]", ", ", t)
    t = re.sub(r"\s*\(\s*", ", ", t)
    t = re.sub(r"\s*\)\s*", ", ", t)
    t = t.replace("*", " ")
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([.,!?;:])", r"\1", t)
    t = re.sub(r",\s*,+", ",", t)
    t = re.sub(r",\s*([.!?])", r"\1", t)
    t = re.sub(r"^,\s*", "", t)
    return t


def _check_spoken(spoken: str, index: int, flags: List[str]) -> None:
    if re.search(r"\d", spoken):
        flags.append("unspoken_digits:%d" % index)
    if re.search(r"[=+×÷<>_\[\]#]|[^\x00-\x7F]", spoken):
        flags.append("unspoken_symbol:%d" % index)


def prepare_segment(text: str, *, min_words: int = 4) -> PreparedSegment:
    """Prepare one segment's text for streaming speech. Never raises on odd content; it flags it."""
    if not isinstance(text, str):
        raise TypeError("segment text must be a string, got %s" % type(text).__name__)
    flags: List[str] = []
    cues: List[str] = []
    caption_text = _clean_caption_text(text, flags, cues)
    sentences = _split_cues(_split_sentences(caption_text), cues)
    sentences = _merge_short(sentences, min_words)
    utterances: List[Utterance] = []
    for i, sentence in enumerate(sentences):
        spoken = _speechify(sentence, i, flags)
        if not spoken:
            continue
        _check_spoken(spoken, i, flags)
        if _POSSIBLE_VISUAL.search(sentence):
            flags.append("possible_visual_reference:%d" % i)
        utterances.append(Utterance(caption=sentence, spoken=spoken))
    if not utterances:
        flags.append("no_speakable_text")
    return PreparedSegment(tuple(utterances), tuple(cues), tuple(flags))
