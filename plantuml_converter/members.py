"""Parsing of one line of a class body (field, method or separator), chapter 3.4 to 3.7."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple, Union

from .model import Member, MemberKind, Parameter, Separator, SeparatorStyle, Visibility

_SEPARATOR = re.compile(r"^(?P<m>--|\.\.|==|__)(?:\s*(?P<title>.*?)\s*(?P=m))?$")
_MODIFIER = re.compile(r"\{(?P<name>static|classifier|abstract|field|method)\}", re.IGNORECASE)
_IDENT = re.compile(r"^[\w$]+(?:\[\s*\])*$")
# a colon that is not part of a "::" scope operator
_COLON = re.compile(r"(?<!:):(?!:)")

_OPENERS = "([<{"
_CLOSERS = ")]>}"


def parse_member(text: str, line: int = 0) -> Union[Member, Separator, None]:
    """Parse a body line. Returns ``None`` for an empty line."""
    text = text.strip()
    if not text:
        return None

    sep = _SEPARATOR.match(text)
    if sep:
        return Separator(SeparatorStyle(sep.group("m")), sep.group("title") or None, line)

    is_static = is_abstract = False
    forced: Optional[MemberKind] = None
    visibility: Optional[Visibility] = None

    # Modifiers may be at the start or at the end of the line, visibility right before the name.
    while True:
        text = text.strip()
        mod = _MODIFIER.match(text) or _trailing_modifier(text)
        if mod:
            name = mod.group("name").lower()
            if name in ("static", "classifier"):
                is_static = True
            elif name == "abstract":
                is_abstract = True
            else:
                forced = MemberKind.FIELD if name == "field" else MemberKind.METHOD
            text = text[mod.end() :] if mod.start() == 0 else text[: mod.start()]
            continue
        if visibility is None and text and text[0] in "-#~+" and text[:2] not in ("--", "..", "==", "__"):
            visibility = Visibility(text[0])
            text = text[1:]
            continue
        break

    text = text.strip()
    raw = text
    kind = forced or (MemberKind.METHOD if "(" in text else MemberKind.FIELD)

    member = Member(
        kind=kind,
        name=text,
        raw=raw,
        visibility=visibility,
        is_static=is_static,
        is_abstract=is_abstract,
        line=line,
    )
    if kind is MemberKind.METHOD and "(" in text:
        _fill_method(member, text)
    else:
        _fill_field(member, text)
    return member


def _trailing_modifier(text: str) -> Optional["re.Match[str]"]:
    found = None
    for found in _MODIFIER.finditer(text):
        pass
    if found is not None and text[found.end() :].strip() == "":
        return found
    return None


def _fill_field(member: Member, text: str) -> None:
    default = None
    eq = _top_level_index(text, "=")
    if eq >= 0:
        text, default = text[:eq].strip(), text[eq + 1 :].strip() or None
    member.default_value = default

    colon = _COLON.search(text)
    if colon:  # name : Type
        name, type_ = text[: colon.start()].strip(), text[colon.end() :].strip()
        if name:
            member.name, member.type = name, type_ or None
            return
    split = _split_type_name(text)
    if split:  # Type name
        member.type, member.name = split
    else:
        member.name = text


def _fill_method(member: Member, text: str) -> None:
    open_idx = text.index("(")
    close_idx = _matching_paren(text, open_idx)
    if close_idx < 0:  # unbalanced: keep the whole text as the name
        member.name = text
        return
    head, params, tail = text[:open_idx].strip(), text[open_idx + 1 : close_idx], text[close_idx + 1 :].strip()

    return_type: Optional[str] = None
    name = head
    split = _split_type_name(head)
    if split:  # Type name(...)
        return_type, name = split
    if tail.startswith(":"):  # name(...) : Type
        return_type = tail[1:].strip() or return_type
    elif tail:  # something unexpected after the parameters: keep it visible in the type
        return_type = return_type or tail
    member.name = name or text
    member.type = return_type
    member.parameters = _parse_parameters(params)


def _parse_parameters(params: str) -> List[Parameter]:
    result: List[Parameter] = []
    for part in _split_top_level(params, ","):
        part = part.strip()
        if not part:
            continue
        colon = _COLON.search(part)
        if colon:
            result.append(Parameter(part[: colon.start()].strip(), part[colon.end() :].strip() or None))
            continue
        split = _split_type_name(part)
        if split:
            result.append(Parameter(split[1], split[0]))
        else:
            result.append(Parameter(part))  # a single word: could be a name or a type, kept as name
    return result


def _split_type_name(text: str) -> Optional[Tuple[str, str]]:
    """Split ``Map<String, int> values`` at the last top-level whitespace into (type, name).
    Returns ``None`` when the text is a single word or the last word is not an identifier."""
    text = text.strip()
    depth = 0
    cut = -1
    for i, ch in enumerate(text):
        if ch in _OPENERS:
            depth += 1
        elif ch in _CLOSERS:
            depth -= 1
        elif ch.isspace() and depth <= 0:
            cut = i
    if cut < 0:
        return None
    type_, name = text[:cut].strip(), text[cut:].strip()
    if not type_ or not _IDENT.match(name):
        return None
    return type_, name


def _matching_paren(text: str, open_idx: int) -> int:
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _top_level_index(text: str, char: str) -> int:
    depth = 0
    for i, ch in enumerate(text):
        if ch in _OPENERS:
            depth += 1
        elif ch in _CLOSERS:
            depth -= 1
        elif ch == char and depth <= 0:
            nxt = text[i + 1 : i + 2]
            prev = text[i - 1 : i] if i else ""
            if nxt != "=" and prev not in ("=", "!", "<", ">"):
                return i
    return -1


def _split_top_level(text: str, sep: str) -> List[str]:
    parts: List[str] = []
    depth = 0
    start = 0
    for i, ch in enumerate(text):
        if ch in _OPENERS:
            depth += 1
        elif ch in _CLOSERS:
            depth -= 1
        elif ch == sep and depth <= 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return parts
