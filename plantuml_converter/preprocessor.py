"""First compiler phase: strip comments and cut the text into ``@start...`` blocks."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .diagnostics import Reporter

logger = logging.getLogger(__name__)

_NEWLINE = re.compile(r"\r\n|\r|\n")
_START = re.compile(r"^@start(?P<kind>[A-Za-z][A-Za-z0-9]*)(?P<rest>.*)$", re.IGNORECASE)


@dataclass
class LogicalLine:
    number: int  # 1-based line number in the original text
    text: str  # stripped, comments removed; may be empty (blank lines are kept for notes)


@dataclass
class Block:
    """One ``@startXXX`` ... ``@endXXX`` section of the input."""

    kind: str  # lower-case diagram kind: "uml", "mindmap", "json", ...
    start_line: int
    header: str  # text after the @start keyword, e.g. the diagram name
    lines: List[LogicalLine] = field(default_factory=list)
    end_line: Optional[int] = None  # None when the closing @end... is missing

    @property
    def terminated(self) -> bool:
        return self.end_line is not None


def strip_comments(lines: List[str]) -> List[str]:
    """Remove ``'`` line comments and ``/' ... '/`` block comments.

    Line numbers are preserved: every input line yields exactly one output line.
    A ``'`` only starts a comment at the beginning of a line (PlantUML does not
    support trailing comments, and ``'`` is legal inside labels such as ``don't``).
    Text inside double quotes is never treated as a comment marker.
    """
    result: List[str] = []
    in_block = False
    for raw in lines:
        out: List[str] = []
        i = 0
        in_quote = False
        while i < len(raw):
            if in_block:
                end = raw.find("'/", i)
                if end < 0:
                    i = len(raw)
                else:
                    in_block = False
                    i = end + 2
                continue
            ch = raw[i]
            if ch == '"':
                in_quote = not in_quote
            elif not in_quote and raw.startswith("/'", i):
                in_block = True
                i += 2
                continue
            out.append(ch)
            i += 1
        text = "".join(out)
        if text.lstrip().startswith("'"):
            text = ""
        result.append(text)
    return result


def split_blocks(text: str, reporter: Reporter) -> List[Block]:
    """Cut the input into blocks. Text outside blocks is ignored."""
    physical = _NEWLINE.split(text)
    cleaned = strip_comments(physical)

    blocks: List[Block] = []
    current: Optional[Block] = None
    end_re: Optional[re.Pattern] = None
    outside = 0

    for number, line in enumerate(cleaned, start=1):
        stripped = line.strip()
        start = _START.match(stripped)
        if current is None:
            if start:
                current, end_re = _open_block(start, number)
            elif stripped:
                outside += 1
                logger.debug("line %d: ignored text outside @startuml block: %r", number, stripped)
            continue

        assert end_re is not None
        if end_re.match(stripped):
            current.end_line = number
            logger.debug("block '%s' closed at line %d", current.kind, number)
            blocks.append(current)
            current, end_re = None, None
        elif start:
            # PlantUML would report an error for the unfinished diagram and start a new one.
            reporter.error(
                f"@start{current.kind} at line {current.start_line} is missing its "
                f"@end{current.kind}; new block starts here",
                number,
            )
            blocks.append(current)
            current, end_re = _open_block(start, number)
        else:
            current.lines.append(LogicalLine(number, stripped))

    if current is not None:
        reporter.error(
            f"@start{current.kind} at line {current.start_line} is never closed "
            f"(no @end{current.kind} before end of input)",
            current.start_line,
        )
        blocks.append(current)

    stray = [n for n, line in enumerate(cleaned, 1) if re.match(r"^\s*@end[A-Za-z]+", line)]
    closed = {b.end_line for b in blocks if b.end_line}
    for number in stray:
        if number not in closed:
            reporter.warning("@end without matching @start, ignored", number)

    if outside:
        logger.debug("%d non-empty line(s) outside diagram blocks were ignored", outside)
    return blocks


def _open_block(start: "re.Match[str]", number: int) -> Tuple[Block, re.Pattern]:
    kind = start.group("kind").lower()
    header = _clean_header(start.group("rest"))
    logger.debug("line %d: block '%s' opened (header=%r)", number, kind, header)
    block = Block(kind=kind, start_line=number, header=header)
    return block, re.compile(rf"^@end{kind}\b", re.IGNORECASE)


def _clean_header(rest: str) -> str:
    """``@startuml "My Project"`` / ``@startuml(id=foo)`` / ``@startuml foo.png``."""
    rest = rest.strip()
    if rest.startswith("(") and ")" in rest:
        rest = rest[rest.index(")") + 1 :].strip() or rest
    if len(rest) >= 2 and rest[0] == rest[-1] == '"':
        rest = rest[1:-1]
    return rest
