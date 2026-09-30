"""Second compiler phase: decide whether a ``@startuml`` block is a class diagram.

PlantUML itself decides the diagram type from the first line that only one diagram
type understands. This module does the same:

* a *class marker* (``class Foo``, ``namespace x {``, ``A <|-- B`` ...) makes it a class diagram,
* a *foreign marker* (``participant``, ``component``, ``state``, ``start``, ``[*] --> X`` ...)
  makes it some other diagram type,
* lines that are valid in several diagram types (``A --> B``, ``skinparam``, ``title``,
  ``interface Foo``) are skipped, and the first marker decides.

A diagram without any marker is assumed to be a class diagram: the program is only
fed class diagrams, and the reference guide itself shows ``a -- b`` as a class diagram.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

from .preprocessor import LogicalLine

logger = logging.getLogger(__name__)

_I = re.IGNORECASE

# Keywords that exist only in diagram types other than class diagrams.
_FOREIGN_KEYWORD = re.compile(  # case sensitive on purpose: ``Object : x`` / ``Node o-- Leaf`` are classes
    r"^(?:participant|actor|boundary|control|database|collections|queue|usecase|component|"
    r"node|artifact|storage|agent|person|archimate|state|object|map|json|yaml|salt|"
    r"activate|deactivate|destroy|autonumber|alt|opt|loop|par|critical|break|group|ref|box|"
    r"fork|repeat|while|partition|detach|swimlane|rectangle|cloud|hexagon|"
    r"concise|robust|binary|clock|analog)\b(?=\s+(?:[\"\w(\[]|:\S)|\s*$)"
)
_FOREIGN_PATTERNS = [
    re.compile(r"^(?:start|stop|end|endif|endwhile|end fork|kill|detach)$", _I),  # activity
    re.compile(r"^:.*;$"),  # activity action
    re.compile(r"^(?:if|elseif|while)\s*\(", _I),  # activity
    re.compile(r"^\[\*\]|-->\s*\[\*\]"),  # state diagram
    re.compile(r"^\[[^\]\r\n]+\]\s*(?:[-.<]|$)"),  # component [Name]
    re.compile(r"^\([^),\r\n]+\)\s*(?:[-.<]|as\b|$)", _I),  # use case (Name)
    re.compile(r"^:[^:;\r\n]+:\s*(?:[-.<]|as\b|$)", _I),  # actor :Name:
    re.compile(r"^note\s+over\b", _I),  # sequence
    re.compile(r"^(?:\.\.\.|\|\|\||==[^=].*==)$"),  # sequence delay / spacer / divider
]

_SEQUENCE_ARROW = re.compile(r"->>|<<-")  # only looked for left of the label

# Constructs that only exist in class diagrams.
_CLASS_DECL = re.compile(
    r"^(?:(?:abstract\s+class|abstract|annotation|class|diamond|enum|exception|metaclass|protocol|struct)\s+[\"\w.]|<>\s*\w)", _I
)
_CLASS_PATTERNS = [
    re.compile(r"^(?:namespace|together)\b.*\{$", _I),
    re.compile(r"^set\s+namespaceSeparator\b", _I),
    re.compile(r"^(?:hide|show)\s+.*\b(?:members|fields|attributes|methods|empty)\b", _I),
    re.compile(r"<\|(?:-|\.)|(?:-|\.)\|>"),  # extension / implementation arrows
    re.compile(r"\s(?:extends|implements)\s", _I),
]

_MEMBER_BODY = re.compile(r"^(?:interface|entity|circle|\(\))\b", _I)

# Constructs that open a multi-line text block: the text must not be inspected.
_TEXT_BLOCKS = [
    (re.compile(r"^note\b(?![^:]*:)(?!\s+\"[^\"]*\"\s+as\b)", _I), re.compile(r"^end\s*note$", _I)),
    (re.compile(r"^title$", _I), re.compile(r"^end\s*title$", _I)),
    (re.compile(r"^(?:(?:center|left|right)\s+)?(header|footer)$", _I), re.compile(r"^end\s*(?:header|footer)$", _I)),
    (re.compile(r"^legend\b", _I), re.compile(r"^end\s*legend$", _I)),
]


@dataclass
class Detection:
    is_class_diagram: bool
    reason: str


def detect(lines: List[LogicalLine]) -> Detection:
    """Classify the statements of one ``@startuml`` block."""
    end_of_text: Optional[re.Pattern] = None
    brace_depth = 0

    for line in lines:
        text = line.text
        if not text:
            continue
        if end_of_text is not None:
            if end_of_text.match(text):
                end_of_text = None
            continue
        if brace_depth:
            if text == "}":
                brace_depth -= 1
            elif text.endswith("{"):
                brace_depth += 1
            continue

        if (
            _FOREIGN_KEYWORD.match(text)
            or any(p.search(text) for p in _FOREIGN_PATTERNS)
            or _SEQUENCE_ARROW.search(text.split(":", 1)[0])
        ):
            return Detection(False, f"line {line.number} is not valid in a class diagram: {text!r}")
        if _CLASS_DECL.match(text) or any(p.search(text) for p in _CLASS_PATTERNS):
            return Detection(True, f"line {line.number} is class diagram syntax: {text!r}")

        for opener, closer in _TEXT_BLOCKS:
            if opener.match(text):
                end_of_text = closer
                break
        else:
            if text.endswith("{") and _MEMBER_BODY.match(text):
                brace_depth = 1  # members are not statements; package bodies are, so no skipping there

    return Detection(True, "no diagram-specific syntax found, assuming a class diagram")
