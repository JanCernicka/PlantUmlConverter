"""Third compiler phase: turn the statements of one class diagram into a ``ClassDiagram``.

PlantUML is line oriented, so the parser works statement by statement. Each
``_handle_*`` method recognises one kind of statement and returns ``True`` when it
consumed the line. Lines nobody understands are reported as errors and skipped, so
one bad line never stops the compilation of the rest.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable, List, NamedTuple, Optional, Tuple, Union

from .diagnostics import Reporter
from .members import parse_member
from .model import (
    AssociationClass,
    ArrowHead,
    ClassDiagram,
    ElementKind,
    Entity,
    HeaderFooter,
    LayoutDirection,
    Legend,
    LineStyle,
    Member,
    Note,
    NoteLink,
    NotePosition,
    Package,
    PackageKind,
    Relationship,
    RuleAction,
    RuleFeature,
    RuleTargetKind,
    Spot,
    VisibilityRule,
)
from .preprocessor import Block, LogicalLine
from .relations import NAME, QUOTED, Ref, RelationSyntax, parse_relation

logger = logging.getLogger(__name__)

_I = re.IGNORECASE
_NAME_RE = re.compile(NAME)
_QUOTE_RE = re.compile(QUOTED)
_NAME_OR_QUOTED = rf"(?:{QUOTED}|{NAME})"

_KINDS = {
    "abstract class": ElementKind.ABSTRACT_CLASS,
    "abstract": ElementKind.ABSTRACT_CLASS,
    "annotation": ElementKind.ANNOTATION,
    "circle": ElementKind.CIRCLE,
    "class": ElementKind.CLASS,
    "diamond": ElementKind.DIAMOND,
    "entity": ElementKind.ENTITY,
    "enum": ElementKind.ENUM,
    "exception": ElementKind.EXCEPTION,
    "interface": ElementKind.INTERFACE,
    "metaclass": ElementKind.METACLASS,
    "protocol": ElementKind.PROTOCOL,
    "struct": ElementKind.STRUCT,
    "()": ElementKind.CIRCLE,
    "<>": ElementKind.DIAMOND,
}
_RULE_KINDS = {k: v for k, v in _KINDS.items() if k not in ("()", "<>")}

_DECL = re.compile(
    r"^(?:(?P<kw>abstract\s+class|abstract|annotation|circle|class|diamond|entity|enum|exception|interface|metaclass|protocol|struct)\s+"
    r"|(?P<sym>\(\)|<>)\s*)(?P<rest>\S.*)$",
    _I,
)
_PACKAGE = re.compile(r"^(?P<kw>package|namespace|together)(?:\s+(?P<rest>.*))?$", _I)
_MEMBER_ADD = re.compile(rf"^(?P<ref>{_NAME_OR_QUOTED})\s*:\s*(?P<text>.+)$")
_BARE_STEREOTYPE = re.compile(rf"^(?P<ref>{_NAME_OR_QUOTED})\s*(?P<st>(?:<<.*?>>\s*)+)(?:#(?P<color>[^\s{{]+))?$")
_STEREOTYPE = re.compile(r"<<\s*(.*?)\s*>>")
_SPOT = re.compile(r"^\(\s*(?P<ch>\S)\s*,\s*#?(?P<color>[^)\s]+)\s*\)\s*(?P<name>.*)$")
_INHERIT = re.compile(rf"(?P<kw>extends|implements)\s+(?P<names>{_NAME_OR_QUOTED}(?:\s*,\s*{_NAME_OR_QUOTED})*)", _I)
_ALIAS = re.compile(rf"as\s+(?:(?P<quoted>{QUOTED})|(?P<name>{NAME}))(?=\s|$|<|#|\{{)", _I)
_NAMES_IN_LIST = re.compile(_NAME_OR_QUOTED)

_POSITION = r"(?P<pos>left|right|top|bottom)"
_NOTE_COLOR = r"(?:\s+#(?P<color>[^\s:]+))?"
_NOTE_TEXT = r"\s*(?::\s*(?P<text>.*))?$"
_NOTE_ON_LINK = re.compile(rf"^note\s+(?:{_POSITION}\s+)?on\s+link{_NOTE_COLOR}{_NOTE_TEXT}", _I)
_NOTE_OF = re.compile(rf"^note\s+{_POSITION}\s+of\s+(?P<ref>{_NAME_OR_QUOTED}){_NOTE_COLOR}{_NOTE_TEXT}", _I)
_NOTE_LAST = re.compile(rf"^note\s+{_POSITION}{_NOTE_COLOR}{_NOTE_TEXT}", _I)
_NOTE_FLOATING = re.compile(rf"^note\s+(?:\"(?P<text>[^\"]*)\"\s+)?as\s+(?P<alias>{NAME})(?:\s+#(?P<color>\S+))?$", _I)
_END_NOTE = re.compile(r"^end\s*note$", _I)

_TITLE = re.compile(r"^title(?:\s+(?P<text>.*))?$", _I)
_END_TITLE = re.compile(r"^end\s*title$", _I)
_HEADER_FOOTER = re.compile(r"^(?:(?P<align>center|left|right)\s+)?(?P<kind>header|footer)(?:\s+(?P<text>.*))?$", _I)
_END_HEADER_FOOTER = re.compile(r"^end\s*(?:header|footer)$", _I)
_CAPTION = re.compile(r"^caption\s+(?P<text>.+)$", _I)
_LEGEND = re.compile(r"^legend(?:\s+(?P<align>(?:(?:left|right|center|top|bottom)\s*)+))?$", _I)
_END_LEGEND = re.compile(r"^end\s*legend$", _I)

_SKINPARAM = re.compile(r"^skinparam\s+(?P<name>[^\s<]+(?:\s*<<.*?>>)?)(?:\s+(?P<value>.*))?$", _I)
_SKIN_BLOCK_LINE = re.compile(r"^(?P<name>[^\s<]+(?:\s*<<.*?>>)?)\s+(?P<value>.*)$")
_DIRECTION = re.compile(r"^(?P<d>left\s+to\s+right|top\s+to\s+bottom)\s+direction$", _I)
_SCALE = re.compile(r"^scale\s+(?P<value>(?:max\s+)?\d.*)$", _I)
_PAGE = re.compile(r"^page\s+(?P<h>\d+)\s*x\s*(?P<v>\d+)$", _I)
_SET = re.compile(r"^set\s+(?P<key>[A-Za-z]\w*)(?:\s+(?P<value>.*))?$", _I)
_HIDE_SHOW = re.compile(r"^(?P<action>hide|show)\s+(?P<spec>.+)$", _I)
_RULE_FEATURE = re.compile(r"(?:^|\s)(?:(?P<empty>empty)\s+)?(?P<feature>members|fields|attributes|methods|circle|stereotype)$", _I)
_IGNORED = re.compile(r"^(?:newpage|allowmixing|allow_mixing|mainframe)\b", _I)

_POSITIONS = {p.value: p for p in NotePosition}
_FEATURES = {"members": RuleFeature.MEMBERS, "fields": RuleFeature.FIELDS, "attributes": RuleFeature.FIELDS,
             "methods": RuleFeature.METHODS, "circle": RuleFeature.CIRCLE, "stereotype": RuleFeature.STEREOTYPE}


class _QName(NamedTuple):
    qualified: str  # unique key of the entity
    namespace: Optional[str]
    relative: bool  # written without namespace, so it belongs to the enclosing scope
    simple: str  # last segment of the name


@dataclass
class _Decl:
    """The parts of a declaration line after the keyword."""

    name: str
    quoted: bool = False
    display: Optional[str] = None
    generics: Optional[str] = None
    stereotypes: List[str] = field(default_factory=list)
    spot: Optional[Spot] = None
    color: Optional[str] = None
    extends: List[Ref] = field(default_factory=list)
    implements: List[Ref] = field(default_factory=list)
    brace: bool = False
    inline_body: str = ""  # text after "{" on the same line
    junk: str = ""  # text that could not be understood


class ClassDiagramParser:
    def __init__(self, block: Block, reporter: Reporter) -> None:
        self._lines = block.lines
        self._pos = 0
        self._rep = reporter
        self._sep: Optional[str] = "."
        self.diagram = ClassDiagram(name=block.header or None, start_line=block.start_line, end_line=block.end_line)
        self._stack: List[Package] = [self.diagram.root]
        self._last_entity: Optional[Entity] = None
        self._last_relationship: Optional[Relationship] = None
        self._notes_by_alias: dict = {}
        self._together_count = 0
        self._handlers: List[Callable[[LogicalLine], bool]] = [
            self._handle_directive,
            self._handle_close_brace,
            self._handle_skinparam,
            self._handle_title,
            self._handle_header_footer,
            self._handle_caption,
            self._handle_legend,
            self._handle_settings,
            self._handle_hide_show,
            self._handle_note,
            self._handle_package,
            self._handle_declaration,
            self._handle_relation,
            self._handle_member_add,
            self._handle_bare_stereotype,
            self._handle_ignored,
        ]

    # ------------------------------------------------------------------ driver

    def parse(self) -> ClassDiagram:
        while self._pos < len(self._lines):
            line = self._lines[self._pos]
            self._pos += 1
            if not line.text:
                continue
            for handler in self._handlers:
                if handler(line):
                    break
            else:
                self._rep.error(f"syntax error, cannot parse statement: {line.text!r}", line.number)
        self._finish()
        self.diagram.diagnostics = list(self._rep.items)
        return self.diagram

    def _finish(self) -> None:
        for package in self._stack[1:]:
            self._rep.error(f"{package.kind.value} '{package.qualified_name}' is never closed with '}}'", package.line)
        for rule in self.diagram.rules:
            if rule.target_kind is RuleTargetKind.ENTITY and rule.target is not None:
                entity = self.diagram.get_entity(rule.target)
                if entity:
                    rule.target = entity.qualified_name
                elif self.diagram.get_package(rule.target) is None:
                    self._rep.warning(f"{rule.action.value} refers to unknown class '{rule.target}'", rule.line)

    # ------------------------------------------------------------- reading blocks

    def _read_until(self, end: "re.Pattern[str]", what: str, start_line: int) -> List[str]:
        """Collect lines up to (and consuming) the line matching ``end``."""
        collected: List[str] = []
        while self._pos < len(self._lines):
            line = self._lines[self._pos]
            self._pos += 1
            if end.match(line.text):
                return collected
            collected.append(line.text)
        self._rep.error(f"{what} is never closed", start_line)
        return collected

    def _next_is_open_brace(self) -> bool:
        """``class Foo`` followed by a line with only ``{``: consume the brace."""
        i = self._pos
        while i < len(self._lines) and not self._lines[i].text:
            i += 1
        if i < len(self._lines) and self._lines[i].text == "{":
            self._pos = i + 1
            return True
        return False

    # ----------------------------------------------------------- simple commands

    def _handle_directive(self, line: LogicalLine) -> bool:
        if not line.text.startswith("!"):
            return False
        if line.text.lower().startswith("!pragma"):
            logger.debug("line %d: pragma ignored: %s", line.number, line.text)
        else:
            self._rep.warning(f"preprocessor directive is not supported and was ignored: {line.text!r}", line.number)
        return True

    def _handle_close_brace(self, line: LogicalLine) -> bool:
        if line.text != "}":
            return False
        if len(self._stack) == 1:
            self._rep.error("'}' without matching '{'", line.number)
        else:
            closed = self._stack.pop()
            logger.debug("line %d: closed %s '%s'", line.number, closed.kind.value, closed.qualified_name)
        return True

    def _handle_ignored(self, line: LogicalLine) -> bool:
        if _IGNORED.match(line.text):
            self._rep.warning(f"command is not supported in class diagrams and was ignored: {line.text!r}", line.number)
            return True
        return False

    def _handle_settings(self, line: LogicalLine) -> bool:
        text = line.text
        m = _DIRECTION.match(text)
        if m:
            d = " ".join(m.group("d").lower().split())
            self.diagram.direction = LayoutDirection(d)
            return True
        m = _SCALE.match(text)
        if m:
            self.diagram.scale = m.group("value").strip()
            return True
        m = _PAGE.match(text)
        if m:
            self.diagram.page = (int(m.group("h")), int(m.group("v")))
            return True
        m = _SET.match(text)
        if m:
            key, value = m.group("key"), (m.group("value") or "").strip()
            if key.lower() == "namespaceseparator":
                if not value:
                    self._rep.error("'set namespaceSeparator' needs a value", line.number)
                else:
                    self._sep = None if value.lower() == "none" else value
                    self.diagram.namespace_separator = self._sep
                    logger.debug("line %d: namespace separator is now %r", line.number, self._sep)
            else:
                self._rep.warning(f"unknown setting '{key}' ignored", line.number)
            return True
        return False

    def _handle_skinparam(self, line: LogicalLine) -> bool:
        m = _SKINPARAM.match(line.text)
        if not m:
            return False
        name = _compact_stereotype(m.group("name"))
        value = (m.group("value") or "").strip()
        if value == "{":  # skinparam class { Key Value ... }
            for body in self._read_until(re.compile(r"^\}$"), f"skinparam {name} block", line.number):
                entry = _SKIN_BLOCK_LINE.match(body)
                if entry:
                    self.diagram.skinparams[name + _compact_stereotype(entry.group("name"))] = entry.group("value").strip()
                elif body:
                    self._rep.warning(f"cannot parse skinparam entry {body!r}", line.number)
        elif value:
            self.diagram.skinparams[name] = value
        else:
            self._rep.warning(f"skinparam '{name}' has no value", line.number)
        return True

    # ------------------------------------------------------- title, header, legend

    def _handle_title(self, line: LogicalLine) -> bool:
        m = _TITLE.match(line.text)
        if not m:
            return False
        text = m.group("text")
        if text is None:
            text = "\n".join(self._read_until(_END_TITLE, "title", line.number)).strip("\n")
        self.diagram.title = text
        return True

    def _handle_header_footer(self, line: LogicalLine) -> bool:
        m = _HEADER_FOOTER.match(line.text)
        if not m:
            return False
        text = m.group("text")
        kind = m.group("kind").lower()
        if text is None:
            text = "\n".join(self._read_until(_END_HEADER_FOOTER, kind, line.number)).strip("\n")
        align = m.group("align").lower() if m.group("align") else None
        setattr(self.diagram, kind, HeaderFooter(text, align))
        return True

    def _handle_caption(self, line: LogicalLine) -> bool:
        m = _CAPTION.match(line.text)
        if not m:
            return False
        self.diagram.caption = m.group("text").strip()
        return True

    def _handle_legend(self, line: LogicalLine) -> bool:
        m = _LEGEND.match(line.text)
        if not m:
            return False
        horizontal = vertical = None
        for word in (m.group("align") or "").lower().split():
            if word in ("top", "bottom"):
                vertical = word
            else:
                horizontal = word
        text = "\n".join(self._read_until(_END_LEGEND, "legend", line.number)).strip("\n")
        self.diagram.legend = Legend(text, horizontal, vertical)
        return True

    # ---------------------------------------------------------------- hide / show

    def _handle_hide_show(self, line: LogicalLine) -> bool:
        m = _HIDE_SHOW.match(line.text)
        if not m:
            return False
        spec = m.group("spec").strip()
        if not re.match(r'[\w"]|<<', spec):
            return False  # "hide --> x": a relationship of a class named hide
        rule = VisibilityRule(RuleAction(m.group("action").lower()), line=line.number)
        feature = _RULE_FEATURE.search(spec)
        if feature:
            rule.feature = _FEATURES[feature.group("feature").lower()]
            rule.empty_only = bool(feature.group("empty"))
            spec = spec[: feature.start()].strip()
        if not spec:
            rule.target_kind = RuleTargetKind.ALL
        elif spec.startswith("<<"):
            rule.target_kind = RuleTargetKind.STEREOTYPE
            rule.target = _compact_stereotype(spec)[2:-2] if spec.endswith(">>") else spec
        elif " ".join(spec.lower().split()) in _RULE_KINDS:
            rule.target_kind = RuleTargetKind.ELEMENT_KIND
            rule.target = _RULE_KINDS[" ".join(spec.lower().split())].value
        else:
            rule.target_kind = RuleTargetKind.ENTITY
            rule.target = _unquote(spec)
        if rule.feature is None and rule.target_kind is RuleTargetKind.ALL:
            return False  # nothing recognisable
        self.diagram.rules.append(rule)
        logger.debug("line %d: %s rule %s", line.number, rule.action.value, rule)
        return True

    # ------------------------------------------------------------------- packages

    def _handle_package(self, line: LogicalLine) -> bool:
        m = _PACKAGE.match(line.text)
        if not m:
            return False
        kind = PackageKind(m.group("kw").lower())
        rest = (m.group("rest") or "").strip()

        if kind is PackageKind.TOGETHER:
            if rest != "{":
                return False
            self._together_count += 1
            package = Package("", f"together#{self._together_count}", kind, line=line.number)
            self._attach_package(package)
            return True

        decl = _parse_decl(rest)
        if decl is None:
            return False
        if decl.extends or decl.implements or decl.generics or decl.junk:
            self._rep.warning(f"unexpected text in {kind.value} declaration ignored: {decl.junk or rest!r}", line.number)
        if not decl.brace and not self._next_is_open_brace():
            self._rep.error(f"{kind.value} '{decl.name}' is missing its '{{'", line.number)
            return True

        qualified = self._package_qualified_name(kind, decl.name)
        existing = self.diagram.packages.get(qualified)
        if existing is not None and existing.kind is kind:
            logger.debug("line %d: reopening %s '%s'", line.number, kind.value, qualified)
            self._stack.append(existing)
            self._remember_body_end(decl)
            return True
        package = Package(decl.name, qualified, kind, decl.display, decl.stereotypes, decl.color, line=line.number)
        self._attach_package(package)
        self.diagram.packages[qualified] = package
        logger.debug("line %d: opened %s '%s'", line.number, kind.value, qualified)
        self._remember_body_end(decl)
        return True

    def _remember_body_end(self, decl: _Decl) -> None:
        """A package opened and closed on one line: ``package foo { }``."""
        inline = decl.inline_body.strip()
        if inline.endswith("}"):
            self._stack.pop()
        elif inline:
            self._rep.warning(f"text after '{{' ignored: {inline!r}", self._lines[self._pos - 1].number)

    def _attach_package(self, package: Package) -> None:
        self._stack[-1].children.append(package)
        if package.kind is PackageKind.TOGETHER:
            self.diagram.packages[package.qualified_name] = package
        self._stack.append(package)

    def _package_qualified_name(self, kind: PackageKind, name: str) -> str:
        if kind is PackageKind.NAMESPACE:
            return self._join(self._current_namespace(), name)
        for package in reversed(self._stack[1:]):
            if package.kind is not PackageKind.TOGETHER:
                return self._join(package.qualified_name, name)
        return name

    def _current_namespace(self) -> str:
        for package in reversed(self._stack):
            if package.kind is PackageKind.NAMESPACE:
                return package.qualified_name
        return ""

    def _join(self, prefix: str, name: str) -> str:
        return f"{prefix}{self._sep or '.'}{name}" if prefix else name

    # --------------------------------------------------------------- declarations

    def _handle_declaration(self, line: LogicalLine) -> bool:
        m = _DECL.match(line.text)
        if not m:
            return False
        decl = _parse_decl(m.group("rest"))
        if decl is None:
            return False  # e.g. "class <|-- Foo": a relationship between an entity named "class"
        keyword = " ".join((m.group("kw") or m.group("sym")).lower().split())
        kind = _KINDS[keyword]
        if decl.junk:
            self._rep.warning(f"unexpected text ignored in declaration: {decl.junk!r}", line.number)

        entity = self._declare(kind, decl, line.number)
        for ref in decl.extends:
            self._inherit(entity, ref, ElementKind.CLASS, LineStyle.SOLID, line.number)
        for ref in decl.implements:
            self._inherit(entity, ref, ElementKind.INTERFACE, LineStyle.DOTTED, line.number)

        if decl.brace or self._next_is_open_brace():
            self._read_body(entity, decl.inline_body, line.number)
        return True

    def _declare(self, kind: ElementKind, decl: _Decl, line: int) -> Entity:
        qname = self._qualify(decl.name, decl.quoted)
        qualified = qname.qualified
        entity = self.diagram.entities.get(qualified)
        if entity is None:
            entity = self._create_entity(qname, kind, line, implicit=False)
        elif entity.implicit:
            entity.kind, entity.implicit, entity.line = kind, False, line
            self._move_to(entity, qname.namespace, qname.relative)
            logger.debug("line %d: %s '%s' declared (was implicit)", line, kind.value, qualified)
        elif entity.kind is not kind:
            self._rep.warning(
                f"'{qualified}' is already declared as {entity.kind.value} at line {entity.line}; "
                f"redeclaration as {kind.value} ignored",
                line,
            )
        else:
            logger.debug("line %d: '%s' declared again, merging", line, qualified)
        group = self._stack[-1]
        if group.kind is PackageKind.TOGETHER and entity not in group.children:
            # ``together`` only hints the layout: the entity stays in its package but is also listed here
            group.children.append(entity)

        if decl.display:
            entity.display_name = decl.display
        if decl.generics:
            entity.generics = decl.generics
        for stereotype in decl.stereotypes:
            if stereotype not in entity.stereotypes:
                entity.stereotypes.append(stereotype)
        entity.spot = decl.spot or entity.spot
        entity.color = decl.color or entity.color
        self._last_entity = entity
        return entity

    def _inherit(self, child: Entity, ref: Ref, implicit_kind: ElementKind, style: LineStyle, line: int) -> None:
        parent = self._resolve_entity(ref, line, implicit_kind)
        if parent is None:
            return
        (child.extends if implicit_kind is ElementKind.CLASS else child.implements).append(parent)
        self.diagram.relationships.append(
            Relationship(parent, child, source_head=ArrowHead.EXTENSION, line_style=style, from_declaration=True, line=line)
        )

    def _read_body(self, entity: Entity, inline: str, start_line: int) -> None:
        inline = inline.strip()
        if inline.endswith("}"):  # class Foo { int x }
            body = [inline[:-1]]
        else:
            body = ([inline] if inline else []) + self._read_until(re.compile(r"^\}$"), f"body of '{entity.qualified_name}'", start_line)
        for text in body:
            member = parse_member(text, start_line)
            if member is not None:
                entity.members.append(member)

    # ------------------------------------------------------------- name resolution

    def _qualify(self, raw: str, quoted: bool) -> _QName:
        """Apply the namespace rules of chapter 3.19: ``a.b.Name`` is absolute, ``.Name`` is in
        the default namespace, a plain ``Name`` belongs to the enclosing ``namespace`` block.
        Quoted names are never split."""
        absolute = not quoted and raw.startswith(".")
        name = raw[1:] if absolute else raw
        if not quoted and self._sep and self._sep in name:
            namespace, _, simple = name.rpartition(self._sep)
            return _QName(name, namespace, False, simple)
        if absolute:
            return _QName(name, None, False, name)
        scope = self._current_namespace()
        if scope:
            return _QName(self._join(scope, name), scope, True, name)
        return _QName(name, None, True, name)

    def _create_entity(self, qname: _QName, kind: ElementKind, line: int, implicit: bool) -> Entity:
        entity = Entity(
            name=qname.simple,
            qualified_name=qname.qualified,
            kind=kind,
            namespace=qname.namespace,
            implicit=implicit,
            line=line,
        )
        container = self._container(qname.namespace, qname.relative)
        container.children.append(entity)
        entity.package = container
        self.diagram.entities[qname.qualified] = entity
        logger.debug("line %d: %s %s '%s'", line, "implicit" if implicit else "new", kind.value, qname.qualified)
        return entity

    def _container(self, namespace: Optional[str], relative: bool) -> Package:
        if relative:
            return self._stack[-1]
        if not namespace:
            return self.diagram.root
        package = self.diagram.packages.get(namespace)
        if package is None:
            package = Package(namespace, namespace, PackageKind.NAMESPACE)
            self.diagram.root.children.append(package)
            self.diagram.packages[namespace] = package
            logger.debug("namespace '%s' created automatically", namespace)
        return package

    def _move_to(self, entity: Entity, namespace: Optional[str], relative: bool) -> None:
        target = self._container(namespace, relative)
        if entity.package is target:
            return
        if entity.package is not None:
            entity.package.children.remove(entity)
        target.children.append(entity)
        entity.package = target

    def _resolve_endpoint(self, ref: Ref, line: int, implicit_kind: ElementKind = ElementKind.CLASS) -> Union[Entity, Package, Note]:
        """Find what a name in a relationship refers to; unknown names become implicit classes."""
        qname = self._qualify(ref.text, ref.quoted)
        entity = self.diagram.entities.get(qname.qualified)
        if entity is not None:
            return entity
        if not ref.quoted and ref.text in self._notes_by_alias:
            return self._notes_by_alias[ref.text]
        package = self.diagram.packages.get(ref.text) or self.diagram.get_package(ref.text)
        if package is not None and package.kind is not PackageKind.TOGETHER:
            return package
        entity = self._create_entity(qname, implicit_kind, line, implicit=True)
        self._last_entity = entity
        return entity

    def _resolve_entity(self, ref: Ref, line: int, implicit_kind: ElementKind = ElementKind.CLASS) -> Optional[Entity]:
        target = self._resolve_endpoint(ref, line, implicit_kind)
        if isinstance(target, Entity):
            return target
        self._rep.error(f"'{ref.text}' is a {'note' if isinstance(target, Note) else 'package'}, a class is expected here", line)
        return None

    # -------------------------------------------------------------- relationships

    def _handle_relation(self, line: LogicalLine) -> bool:
        syntax = parse_relation(line.text)
        if syntax is None:
            return False
        if syntax.left.pair or syntax.right.pair:
            self._association_class(syntax, line.number)
            return True

        left = self._resolve_endpoint(syntax.left, line.number)
        right = self._resolve_endpoint(syntax.right, line.number)
        for unknown in syntax.style.unknown:
            self._rep.warning(f"unknown link style '{unknown}' ignored", line.number)

        if isinstance(left, Note) or isinstance(right, Note):
            self._note_link(left, right, syntax, line.number)
            return True

        style = syntax.style
        relationship = Relationship(
            source=left,
            target=right,
            source_head=syntax.left_head,
            target_head=syntax.right_head,
            line_style=style.line_style or (LineStyle.DOTTED if syntax.dotted else LineStyle.SOLID),
            length=syntax.length,
            direction=syntax.direction,
            bold=style.bold,
            hidden=style.hidden,
            color=style.color,
            text_color=style.text_color,
            thickness=style.thickness,
            label=syntax.label,
            label_arrow=syntax.label_arrow,
            source_cardinality=syntax.left_cardinality,
            target_cardinality=syntax.right_cardinality,
            source_qualifier=syntax.left_qualifier,
            target_qualifier=syntax.right_qualifier,
            line=line.number,
        )
        self.diagram.relationships.append(relationship)
        self._last_relationship = relationship
        logger.debug("line %d: %r", line.number, relationship)
        return True

    def _note_link(self, left: object, right: object, syntax: RelationSyntax, line: int) -> None:
        if isinstance(left, Note) and isinstance(right, Note):
            self._rep.error("a link between two notes is not supported", line)
            return
        note, target = (left, right) if isinstance(left, Note) else (right, left)
        if syntax.left_head is not ArrowHead.NONE or syntax.right_head is not ArrowHead.NONE:
            self._rep.warning("arrow heads on a note link are ignored", line)
        self.diagram.note_links.append(
            NoteLink(note, target, LineStyle.DOTTED if syntax.dotted else LineStyle.SOLID, line)  # type: ignore[arg-type]
        )

    def _association_class(self, syntax: RelationSyntax, line: int) -> None:
        """``(Student, Course) .. Enrollment`` (either side may hold the pair)."""
        if syntax.left.pair and syntax.right.pair:
            self._rep.error("both sides of a link are association pairs", line)
            return
        pair_ref, other = (syntax.left, syntax.right) if syntax.left.pair else (syntax.right, syntax.left)
        assert pair_ref.pair is not None
        first = self._resolve_entity(pair_ref.pair[0], line)
        second = self._resolve_entity(pair_ref.pair[1], line)
        entity = self._resolve_entity(other, line)
        if first is None or second is None or entity is None:
            return
        if syntax.left_head is not ArrowHead.NONE or syntax.right_head is not ArrowHead.NONE:
            self._rep.warning("arrow heads on an association class link are ignored", line)
        link = next(
            (r for r in reversed(self.diagram.relationships) if {id(r.source), id(r.target)} == {id(first), id(second)}),
            None,
        )
        if link is None:
            self._rep.warning(f"no relationship between '{first.qualified_name}' and '{second.qualified_name}' defined before the association class", line)
        self.diagram.association_classes.append(
            AssociationClass(first, second, entity, link, LineStyle.DOTTED if syntax.dotted else LineStyle.SOLID, line)
        )

    # -------------------------------------------------------------------- members

    def _handle_member_add(self, line: LogicalLine) -> bool:
        m = _MEMBER_ADD.match(line.text)
        if not m:
            return False
        ref = _ref_from_text(m.group("ref"))
        entity = self._resolve_entity(ref, line.number)
        if entity is None:
            return True
        member = parse_member(m.group("text"), line.number)
        if member is not None:
            entity.members.append(member)
            self._last_entity = entity
            logger.debug("line %d: member added to '%s'", line.number, entity.qualified_name)
        return True

    def _handle_bare_stereotype(self, line: LogicalLine) -> bool:
        """``Class01 <<Foo>>``: declares a class and gives it a stereotype."""
        m = _BARE_STEREOTYPE.match(line.text)
        if not m:
            return False
        ref = _ref_from_text(m.group("ref"))
        decl = _Decl(ref.text, ref.quoted, color=m.group("color"))
        for stereotype in _STEREOTYPE.findall(m.group("st")):
            _add_stereotype(decl, stereotype)
        self._declare(ElementKind.CLASS, decl, line.number)
        return True

    # ---------------------------------------------------------------------- notes

    def _handle_note(self, line: LogicalLine) -> bool:
        text = line.text
        if not re.match(r"^note\b", text, _I):
            return False

        m = _NOTE_ON_LINK.match(text)
        if m:
            if self._last_relationship is None:
                self._rep.error("'note on link' without a preceding relationship", line.number)
                self._skip_note_text(m.group("text"), line.number)
                return True
            note = self._finish_note(m, line.number, self._last_relationship)
            self._last_relationship.note = note
            return True

        m = _NOTE_OF.match(text)
        if m:
            ref = _ref_from_text(m.group("ref"))
            entity, member = self._split_member_ref(ref, line.number)
            if entity is not None:  # note right of Class::member
                note = self._finish_note(m, line.number, entity)
                note.member = member
                return True
            target = self._resolve_endpoint(ref, line.number)
            if isinstance(target, Note):
                self._rep.error("a note cannot be attached to another note", line.number)
                self._skip_note_text(m.group("text"), line.number)
                return True
            self._finish_note(m, line.number, target)
            return True

        m = _NOTE_FLOATING.match(text)
        if m:
            alias = m.group("alias")
            note = Note(m.group("text") or "", alias=alias, color=m.group("color"), line=line.number)
            if m.group("text") is None:
                note.text = "\n".join(self._read_until(_END_NOTE, f"note '{alias}'", line.number)).strip("\n")
            if alias in self._notes_by_alias:
                self._rep.warning(f"note alias '{alias}' is defined twice", line.number)
            self._notes_by_alias[alias] = note
            self.diagram.notes.append(note)
            return True

        m = _NOTE_LAST.match(text)
        if m:
            if self._last_entity is None:
                self._rep.error("note without target: no class was defined before it", line.number)
                self._skip_note_text(m.group("text"), line.number)
                return True
            self._finish_note(m, line.number, self._last_entity)
            return True
        return False

    def _split_member_ref(self, ref: Ref, line: int) -> Tuple[Optional[Entity], str]:
        """``Class::member`` names a member of an existing class, unless ``::`` is the
        namespace separator. Returns (class, member) or (None, "")."""
        if ref.quoted or self._sep == "::" or "::" not in ref.text:
            return None, ""
        owner_text, _, member = ref.text.rpartition("::")
        owner = self.diagram.entities.get(self._qualify(owner_text, False).qualified)
        if owner is None or not member:
            return None, ""
        if not any(isinstance(m, Member) and m.name == member.rstrip("()") for m in owner.members):
            self._rep.warning(f"'{owner.qualified_name}' has no member '{member}'", line)
        return owner, member

    def _finish_note(self, m: "re.Match[str]", line: int, target: Union[Entity, Package, Relationship]) -> Note:
        body = m.group("text")
        if body is None:
            body = "\n".join(self._read_until(_END_NOTE, "note", line)).strip("\n")
        position = m.groupdict().get("pos")
        note = Note(body, _POSITIONS[position.lower()] if position else None, target, color=m.group("color"), line=line)
        self.diagram.notes.append(note)
        return note

    def _skip_note_text(self, single_line: Optional[str], line: int) -> None:
        if single_line is None:
            self._read_until(_END_NOTE, "note", line)


# ------------------------------------------------------------------------ helpers


def _parse_decl(rest: str) -> Optional[_Decl]:
    """Parse ``Name as "Label" <T> <<Stereo>> #color extends A implements B {``."""
    s = rest.strip()
    first = _QUOTE_RE.match(s) or _NAME_RE.match(s)
    if not first:
        return None
    first_quoted = s[0] == '"'
    first_text = _unquote(first.group()) if first_quoted else first.group()
    decl = _Decl(name=first_text, quoted=first_quoted)
    pos = first.end()

    while True:
        while pos < len(s) and s[pos].isspace():
            pos += 1
        if pos >= len(s):
            break
        tail = s[pos:]
        if tail.startswith("<<"):
            m = _STEREOTYPE.match(tail)
            if not m:
                decl.junk = tail
                break
            _add_stereotype(decl, m.group(1))
            pos += m.end()
        elif tail[0] == "<":
            end = _matching_angle(tail)
            if end < 0:
                decl.junk = tail
                break
            decl.generics = tail[1:end].strip()
            pos += end + 1
        elif tail[0] == "#":
            m = re.match(r"#([^\s{]+)", tail)
            if not m:
                decl.junk = tail
                break
            decl.color = m.group(1)
            pos += m.end()
        elif tail[0] == "{":
            decl.brace = True
            decl.inline_body = tail[1:]
            break
        else:
            alias = _ALIAS.match(tail)
            inherit = _INHERIT.match(tail)
            if alias:
                if alias.group("quoted"):  # Name as "Label"
                    decl.display = _unquote(alias.group("quoted"))
                else:  # "Label" as Name
                    decl.display = first_text
                    decl.name, decl.quoted = alias.group("name"), False
                pos += alias.end()
            elif inherit:
                refs = [_ref_from_text(n) for n in _NAMES_IN_LIST.findall(inherit.group("names"))]
                (decl.extends if inherit.group("kw").lower() == "extends" else decl.implements).extend(refs)
                pos += inherit.end()
            else:
                decl.junk = tail
                break
    return decl


def _add_stereotype(decl: _Decl, content: str) -> None:
    spot = _SPOT.match(content)
    if spot:
        decl.spot = Spot(spot.group("ch"), spot.group("color"))
        content = spot.group("name").strip()
    if content:
        decl.stereotypes.append(content)


def _matching_angle(text: str) -> int:
    depth = 0
    for i, ch in enumerate(text):
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _compact_stereotype(text: str) -> str:
    """``BackgroundColor<< Foo >>`` -> ``BackgroundColor<<Foo>>``."""
    return re.sub(r"<<\s*(.*?)\s*>>", r"<<\1>>", text)


def _unquote(text: str) -> str:
    text = text.strip()
    return text[1:-1].strip() if len(text) >= 2 and text[0] == text[-1] == '"' else text


def _ref_from_text(text: str) -> Ref:
    return Ref(_unquote(text), quoted=text.startswith('"'))
