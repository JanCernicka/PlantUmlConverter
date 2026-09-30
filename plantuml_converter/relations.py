"""Syntax of relationship lines, chapter 3.2, 3.3, 3.21 to 3.24 and 3.31 to 3.32.

This module only *recognises* the text. Resolving names to entities and building
``Relationship`` objects is done by the parser.

    Left "1" *-- "many" Right #red : label >
    (Student, Course) .. Enrollment
    foo -[#red,dashed]-> bar
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .model import ArrowHead, Direction, LineStyle

_WORD = r"[\w$]+"
NAME = rf"\.?{_WORD}(?:(?:\.|::){_WORD})*"
QUOTED = r'"[^"]*"'

_REF = re.compile(rf"(?P<quoted>{QUOTED})|(?P<pair>\(\s*(?P<p1>{NAME}|{QUOTED})\s*,\s*(?P<p2>{NAME}|{QUOTED})\s*\))|(?P<name>{NAME})")
_QUOTE = re.compile(QUOTED)
_QUALIFIER = re.compile(r"\[([^\]]*)\]")
_WS = re.compile(r"\s*")

_ARROW = re.compile(
    r"""
    (?P<lh><\||<(?!<)|\*|o(?=[-.])|\#|x(?=[-.])|\}|\+|\^|\(\))?
    (?P<b1>[-.]+)
    (?:\[(?P<style>[^\]]*)\])?
    (?:(?P<dir>left|right|up|down|le|ri|do|u|d|l|r)(?=[-.\[]))?
    (?:\[(?P<style2>[^\]]*)\])?
    (?P<sock>\(0\)|0\)|\(0)?
    (?P<b2>[-.]*)
    (?P<rh>\|>|>(?!>)|\*|o(?![\w$])|\#|x(?![\w$])|\{|\}|\+|\^|\(\))?
    """,
    re.VERBOSE,
)

_LEFT_HEADS = {
    "<|": ArrowHead.EXTENSION,
    "<": ArrowHead.ARROW,
    "*": ArrowHead.COMPOSITION,
    "o": ArrowHead.AGGREGATION,
    "x": ArrowHead.CROSS,
    "#": ArrowHead.HASH,
    "}": ArrowHead.CROWFOOT,
    "+": ArrowHead.PLUS,
    "^": ArrowHead.CARET,
    "()": ArrowHead.LOLLIPOP,
}
_RIGHT_HEADS = {
    "|>": ArrowHead.EXTENSION,
    ">": ArrowHead.ARROW,
    "*": ArrowHead.COMPOSITION,
    "o": ArrowHead.AGGREGATION,
    "x": ArrowHead.CROSS,
    "#": ArrowHead.HASH,
    "{": ArrowHead.CROWFOOT,
    "}": ArrowHead.CROWFOOT,
    "+": ArrowHead.PLUS,
    "^": ArrowHead.CARET,
    "()": ArrowHead.LOLLIPOP,
}
_DIRECTIONS = {"l": Direction.LEFT, "r": Direction.RIGHT, "u": Direction.UP, "d": Direction.DOWN}


@dataclass
class Ref:
    """A name in a relationship: plain, quoted or an association pair ``(A, B)``."""

    text: str = ""
    quoted: bool = False
    pair: Optional[Tuple["Ref", "Ref"]] = None


@dataclass
class LinkStyle:
    line_style: Optional[LineStyle] = None  # explicit [dashed] / [dotted] / [plain]
    bold: bool = False
    hidden: bool = False
    norank: bool = False
    color: Optional[str] = None  # without the leading '#'
    text_color: Optional[str] = None
    thickness: Optional[int] = None
    unknown: List[str] = field(default_factory=list)


@dataclass
class RelationSyntax:
    left: Ref
    right: Ref
    left_head: ArrowHead = ArrowHead.NONE
    right_head: ArrowHead = ArrowHead.NONE
    dotted: bool = False
    length: int = 1
    socket: Optional[str] = None
    direction: Optional[Direction] = None
    style: LinkStyle = field(default_factory=LinkStyle)
    left_cardinality: Optional[str] = None
    right_cardinality: Optional[str] = None
    left_qualifier: Optional[str] = None
    right_qualifier: Optional[str] = None
    label: Optional[str] = None
    label_arrow: Optional[str] = None


def parse_relation(text: str) -> Optional[RelationSyntax]:
    """Return the parsed relationship or ``None`` if ``text`` is not a relationship line."""
    left_match = _REF.match(text)
    if not left_match:
        return None
    left = _ref(left_match)
    pos = _skip(text, left_match.end())

    left_card = left_qualifier = None
    while True:  # "1" and [qualifier] may follow the left name, in any order
        quote = _QUOTE.match(text, pos)
        qualifier = _QUALIFIER.match(text, pos)
        if quote and left_card is None:
            left_card = _unquote(quote.group())
            pos = _skip(text, quote.end())
        elif qualifier and left_qualifier is None:
            left_qualifier = qualifier.group(1).strip()
            pos = _skip(text, qualifier.end())
        else:
            break

    arrow = _ARROW.match(text, pos)
    if not arrow:
        return None
    pos = _skip(text, arrow.end())

    right_card = right_qualifier = None
    right_match = None
    while True:
        qualifier = _QUALIFIER.match(text, pos)
        quote = _QUOTE.match(text, pos)
        if qualifier and right_qualifier is None:
            right_qualifier = qualifier.group(1).strip()
            pos = _skip(text, qualifier.end())
            continue
        if quote and right_card is None:
            candidate = _REF.match(text, _skip(text, quote.end()))
            if candidate:  # "card" Name
                right_card = _unquote(quote.group())
                pos = _skip(text, quote.end())
                continue
        break
    right_match = _REF.match(text, pos)  # plain Name, or a quoted name without cardinality
    if not right_match:
        return None
    pos = right_match.end()
    right = _ref(right_match)

    tail = _parse_tail(text[pos:])
    if tail is None:
        return None
    color_spec, label = tail

    syntax = RelationSyntax(
        left=left,
        right=right,
        left_head=_LEFT_HEADS.get(arrow.group("lh") or "", ArrowHead.NONE),
        right_head=_RIGHT_HEADS.get(arrow.group("rh") or "", ArrowHead.NONE),
        dotted="." in arrow.group("b1") + arrow.group("b2"),
        length=len(arrow.group("b1")) + len(arrow.group("b2")),
        socket=arrow.group("sock"),
        left_cardinality=left_card or None,
        right_cardinality=right_card or None,
        left_qualifier=left_qualifier,
        right_qualifier=right_qualifier,
    )
    if arrow.group("dir"):
        syntax.direction = _DIRECTIONS[arrow.group("dir")[0]]
    for group in ("style", "style2"):
        if arrow.group(group) is not None:
            _apply_inline_style(syntax.style, arrow.group(group))
    if color_spec:
        _apply_color_spec(syntax.style, color_spec)
    if label is not None:
        syntax.label, syntax.label_arrow = split_label_arrow(label)
    return syntax


# ------------------------------------------------------------------------ helpers


def _ref(match: "re.Match[str]") -> Ref:
    if match.group("pair"):
        return Ref(pair=(_name_ref(match.group("p1")), _name_ref(match.group("p2"))))
    if match.group("quoted"):
        return Ref(_unquote(match.group("quoted")), quoted=True)
    return Ref(match.group("name"))


def _name_ref(text: str) -> Ref:
    return Ref(_unquote(text), True) if text.startswith('"') else Ref(text)


def _unquote(text: str) -> str:
    return text[1:-1].strip()


def _skip(text: str, pos: int) -> int:
    return _WS.match(text, pos).end()  # type: ignore[union-attr]


def _parse_tail(tail: str) -> Optional[Tuple[Optional[str], Optional[str]]]:
    """Text after the right name: ``[#color-spec] [: label]``. ``None`` if it is neither."""
    tail = tail.strip()
    color = None
    if tail.startswith("#"):
        token = re.match(r"#\S*", tail).group()  # type: ignore[union-attr]
        tail = tail[len(token) :].strip()
        if token.endswith(":"):  # "#red: label" - the colon belongs to the label separator
            token = token[:-1]
            tail = ":" + tail
        color = token[1:]
    if not tail:
        return color, None
    if tail.startswith(":"):
        return color, tail[1:].strip()
    return None


def split_label_arrow(label: str) -> Tuple[Optional[str], Optional[str]]:
    """``drives >`` -> (``drives``, ``>``); ``< owns`` -> (``owns``, ``<``)."""
    label = label.strip()
    if label in ("<", ">"):
        return None, label
    start = re.match(r"^([<>])\s+(.*)$", label)
    if start:
        return start.group(2).strip() or None, start.group(1)
    end = re.match(r"^(.*?)\s+([<>])$", label)
    if end:
        return end.group(1).strip() or None, end.group(2)
    return (label or None), None


def _apply_inline_style(style: LinkStyle, text: str) -> None:
    """Content of ``-[...]->``: ``#red``, ``bold``, ``dashed``, ``thickness=2`` ..."""
    for token in re.split(r"[,;]", text):
        token = token.strip()
        if not token:
            continue
        low = token.lower()
        if token.startswith("#"):
            style.color = style.color or token[1:]
        elif low == "bold":
            style.bold = True
        elif low == "dashed":
            style.line_style = LineStyle.DASHED
        elif low == "dotted":
            style.line_style = LineStyle.DOTTED
        elif low == "plain":
            style.line_style = LineStyle.SOLID
        elif low == "hidden":
            style.hidden = True
        elif low == "norank":
            style.norank = True
        elif low.startswith("thickness="):
            try:
                style.thickness = int(low.split("=", 1)[1])
            except ValueError:
                style.unknown.append(token)
        else:
            style.unknown.append(token)


def _apply_color_spec(style: LinkStyle, spec: str) -> None:
    """New style notation: ``#line:red;line.bold;text:red`` or ``#green;line.dashed``."""
    for token in spec.split(";"):
        token = token.strip().lstrip("#")
        low = token.lower()
        if not token:
            continue
        if low.startswith("line:"):
            style.color = token[5:]
        elif low.startswith("text:"):
            style.text_color = token[5:]
        elif low.startswith("line."):
            _apply_inline_style(style, token[5:])
        elif style.color is None and ":" not in token:
            style.color = token
        else:
            style.unknown.append(token)
