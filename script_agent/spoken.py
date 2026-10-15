"""Deterministic spoken-text helpers. They never change a number or an operation, only how a symbol is written."""
from __future__ import annotations
import re

_LABEL=re.compile(r'^\s*L\d+\s*[:.\-–—]?\s+',re.I)
_SUBKEY=re.compile(r'(?:^|_)l(\d+)(?:_|$)',re.I)
# A symbol is replaced only when a digit sits on its left and a digit on its right, so hyphens in words
# ("ten-frame"), dashes and ranges like 2020-2021 (no spaces) are left alone.
_SYMBOLS=[
    (re.compile(r'(?<=\d)\s*×\s*(?=\d)'),' times '),
    (re.compile(r'(?<=\d)\s*÷\s*(?=\d)'),' divided by '),
    (re.compile(r'(?<=\d)\s+[-−–]\s+(?=\d)'),' minus '),
    (re.compile(r'(?<=\d)\s*\+\s*(?=\d)'),' plus '),
    (re.compile(r'(?<=\d)\s*=\s*(?=\d)'),' equals '),
]

def strip_label(title):
    """'L1 Ten-frame with 9 dots' -> 'Ten-frame with 9 dots'. The L-number is a card-internal sub-lesson tag."""
    return _LABEL.sub('',title or '').strip()

def subkey(item_id):
    """Sub-lesson number from an id such as ex_l3_51_20 or exp_L12_x; None when the id has none."""
    match=_SUBKEY.search(item_id or '')
    return match.group(1) if match else None

def spoken_math(text):
    for pattern,word in _SYMBOLS:text=pattern.sub(word,text)
    return re.sub(r'[ \t]{2,}',' ',text)

def assemble_template(template,content):
    """Insert the protected passage with spaces at its boundaries; its words stay intact."""
    if '<CONTENT>' not in template:return template.strip()
    left,_,right=template.partition('<CONTENT>')
    content=content.strip();left=left.rstrip();right=right.lstrip()
    if not content:return (left+(' ' if left and right else '')+right).strip()
    before=' ' if left else ''
    after=' ' if right and right[0] not in ',.;:!?' else ''
    return (left+before+content+after+right).strip()
