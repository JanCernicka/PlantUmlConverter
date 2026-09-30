"""Object model of a PlantUML class diagram.

The parser builds these objects; nothing in here knows about PlantUML text.
Relationships, notes and rules refer to ``Entity`` / ``Package`` objects directly
(identity based), so the model is a real object graph, not a bag of strings.
``plantuml_converter.serialize`` turns it into plain dictionaries / JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterator, List, Optional, Tuple, Union

from .diagnostics import Diagnostic

__all__ = [
    "ElementKind",
    "Visibility",
    "MemberKind",
    "SeparatorStyle",
    "PackageKind",
    "ArrowHead",
    "LineStyle",
    "Direction",
    "RelationKind",
    "NotePosition",
    "RuleAction",
    "RuleFeature",
    "RuleTargetKind",
    "LayoutDirection",
    "Parameter",
    "Member",
    "Separator",
    "Spot",
    "Entity",
    "Package",
    "Relationship",
    "Note",
    "NoteLink",
    "AssociationClass",
    "VisibilityRule",
    "HeaderFooter",
    "Legend",
    "ClassDiagram",
    "Endpoint",
]

# --------------------------------------------------------------------------- enums


class ElementKind(Enum):
    """Kinds of elements from chapter 3.1 of the language reference, plus the newer
    ``exception``, ``struct``, ``protocol``, ``metaclass``, ``stereotype``, ``object`` and ``map``.

    ``abstract`` / ``abstract class`` are one kind, so are ``circle`` / ``()``
    and ``diamond`` / ``<>``.
    """

    CLASS = "class"
    ABSTRACT_CLASS = "abstract class"
    INTERFACE = "interface"
    ENUM = "enum"
    ANNOTATION = "annotation"
    ENTITY = "entity"
    CIRCLE = "circle"
    DIAMOND = "diamond"
    # Not in the 1.2020.22 guide, but valid in newer PlantUML class diagrams:
    EXCEPTION = "exception"
    STRUCT = "struct"
    PROTOCOL = "protocol"
    METACLASS = "metaclass"
    STEREOTYPE = "stereotype"
    OBJECT = "object"  # body lines ``name = value`` are fields with a default value
    MAP = "map"  # body lines ``key => value`` are fields: name is the key, default_value the value
    # Elements of other diagram types, only accepted after ``allowmixing``:
    COMPONENT = "component"
    ACTOR = "actor"
    DATABASE = "database"
    USECASE = "usecase"
    NODE = "node"
    ARTIFACT = "artifact"
    STORAGE = "storage"
    QUEUE = "queue"
    BOUNDARY = "boundary"
    CONTROL = "control"
    COLLECTIONS = "collections"
    AGENT = "agent"
    RECTANGLE = "rectangle"
    CLOUD = "cloud"
    HEXAGON = "hexagon"
    PERSON = "person"
    CARD = "card"
    FILE = "file"
    LABEL = "label"
    FOLDER = "folder"
    FRAME = "frame"


class Visibility(Enum):
    PRIVATE = "-"
    PROTECTED = "#"
    PACKAGE_PRIVATE = "~"
    PUBLIC = "+"


class MemberKind(Enum):
    FIELD = "field"
    METHOD = "method"


class SeparatorStyle(Enum):
    """Separators inside a class body: ``--``, ``..``, ``==`` and ``__``."""

    DASHED = "--"
    DOTTED = ".."
    DOUBLE = "=="
    UNDERLINE = "__"


class PackageKind(Enum):
    ROOT = "root"  # the implicit top level container
    PACKAGE = "package"
    NAMESPACE = "namespace"
    TOGETHER = "together"


class ArrowHead(Enum):
    """Decoration at one end of a relationship, named after what it means.
    The value is the symbol as written on the *left* side of the arrow."""

    NONE = ""
    EXTENSION = "<|"
    COMPOSITION = "*"
    AGGREGATION = "o"
    ARROW = "<"
    CROSS = "x"
    HASH = "#"
    CROWFOOT = "}"
    PLUS = "+"
    CARET = "^"
    LOLLIPOP = "()"


class LineStyle(Enum):
    SOLID = "solid"  # --
    DOTTED = "dotted"  # ..
    DASHED = "dashed"  # -[dashed]-


class Direction(Enum):
    """Explicit direction keyword inside an arrow, e.g. ``-left->``."""

    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


class RelationKind(Enum):
    """Semantic reading of a relationship, derived from its heads and line."""

    EXTENSION = "extension"  # <|--
    IMPLEMENTATION = "implementation"  # <|..
    COMPOSITION = "composition"  # *--
    AGGREGATION = "aggregation"  # o--
    DEPENDENCY = "dependency"  # ..>
    DIRECTED_ASSOCIATION = "directed association"  # -->
    ASSOCIATION = "association"  # --
    NESTED = "nested"  # +--
    LOLLIPOP = "lollipop"  # ()--
    SOCKET = "socket"  # -0)-  -(0-  -(0)-
    OTHER = "other"  # x--, #--, }--, ^--, mixed heads


class NotePosition(Enum):
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"


class RuleAction(Enum):
    HIDE = "hide"
    SHOW = "show"
    REMOVE = "remove"  # like hide, but the element takes no space in the layout
    RESTORE = "restore"  # undoes remove


class RuleFeature(Enum):
    """What a ``hide`` / ``show`` command switches. ``None`` means the class itself."""

    MEMBERS = "members"
    FIELDS = "fields"  # also written "attributes"
    METHODS = "methods"
    CIRCLE = "circle"
    STEREOTYPE = "stereotype"


class RuleTargetKind(Enum):
    ALL = "all"  # hide members
    ELEMENT_KIND = "element kind"  # hide class / interface / enum ...
    STEREOTYPE = "stereotype"  # hide <<Foo>> circle
    ENTITY = "entity"  # hide Foo methods
    TAG = "tag"  # hide $tag
    UNLINKED = "unlinked"  # hide @unlinked


class LayoutDirection(Enum):
    LEFT_TO_RIGHT = "left to right"
    TOP_TO_BOTTOM = "top to bottom"


# ------------------------------------------------------------------ class members


@dataclass
class Parameter:
    name: str
    type: Optional[str] = None
    default_value: Optional[str] = None


@dataclass
class Member:
    """A field or a method of an entity."""

    kind: MemberKind
    name: str
    raw: str  # the member text without visibility character and {static}-style modifiers
    visibility: Optional[Visibility] = None
    type: Optional[str] = None  # field type or method return type
    parameters: List[Parameter] = field(default_factory=list)
    is_static: bool = False
    is_abstract: bool = False
    default_value: Optional[str] = None
    line: int = 0


@dataclass
class Separator:
    """Visual separator between groups of members, optionally titled."""

    style: SeparatorStyle
    title: Optional[str] = None
    line: int = 0


@dataclass
class Spot:
    """Custom spotted character from ``<< (S,#FF7700) Singleton >>``."""

    character: str
    color: str


# --------------------------------------------------------------------- containers


@dataclass(eq=False)
class Entity:
    """A class, interface, enum, annotation, abstract class, entity, circle or diamond."""

    name: str  # simple name, last segment of the qualified name
    qualified_name: str  # unique key inside the diagram
    kind: ElementKind = ElementKind.CLASS
    display_name: Optional[str] = None  # label from ``class "Long name" as alias``
    namespace: Optional[str] = None  # qualified name of the namespace, if any
    package: Optional["Package"] = field(default=None, repr=False)  # container in the tree
    generics: Optional[str] = None  # text between < > in ``class Foo<T>``
    stereotypes: List[str] = field(default_factory=list)
    spot: Optional[Spot] = None
    color: Optional[str] = None  # as written after '#', may be a spec like "pink;line:red;line.dashed"
    url: Optional[str] = None  # ``class Foo [[https://example.com{tooltip}]]``
    tooltip: Optional[str] = None
    tags: List[str] = field(default_factory=list)  # ``class Foo $tag``, without the '$'
    extends: List["Entity"] = field(default_factory=list)  # from ``extends`` keyword
    implements: List["Entity"] = field(default_factory=list)  # from ``implements`` keyword
    members: List[Union[Member, Separator]] = field(default_factory=list)
    implicit: bool = False  # created by a reference, never declared
    line: int = 0

    @property
    def fields(self) -> List[Member]:
        return [m for m in self.members if isinstance(m, Member) and m.kind is MemberKind.FIELD]

    @property
    def methods(self) -> List[Member]:
        return [m for m in self.members if isinstance(m, Member) and m.kind is MemberKind.METHOD]

    @property
    def is_abstract(self) -> bool:
        return self.kind is ElementKind.ABSTRACT_CLASS

    def __repr__(self) -> str:
        return f"Entity({self.kind.value} {self.qualified_name!r})"


@dataclass(eq=False)
class Package:
    """A ``package``, ``namespace`` or ``together`` group (or the diagram root)."""

    name: str
    qualified_name: str
    kind: PackageKind = PackageKind.PACKAGE
    display_name: Optional[str] = None
    stereotypes: List[str] = field(default_factory=list)
    color: Optional[str] = None
    url: Optional[str] = None
    tooltip: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    children: List[Union[Entity, "Package"]] = field(default_factory=list)
    line: int = 0

    def iter_entities(self, recursive: bool = True) -> Iterator[Entity]:
        for child in self.children:
            if isinstance(child, Entity):
                yield child
            elif recursive:
                yield from child.iter_entities(True)

    def __repr__(self) -> str:
        return f"Package({self.kind.value} {self.qualified_name!r}, {len(self.children)} children)"


Endpoint = Union[Entity, Package]

# ------------------------------------------------------------------- relationships


@dataclass(eq=False)
class Relationship:
    """A link between two entities (or packages). ``source`` is the left operand
    as written in the text, ``target`` the right one."""

    source: Endpoint
    target: Endpoint
    source_head: ArrowHead = ArrowHead.NONE
    target_head: ArrowHead = ArrowHead.NONE
    line_style: LineStyle = LineStyle.SOLID
    length: int = 1  # number of "-" / "." characters; 1 means horizontal, 2+ vertical
    direction: Optional[Direction] = None  # explicit ``-left->`` keyword
    bold: bool = False
    hidden: bool = False
    color: Optional[str] = None
    text_color: Optional[str] = None
    thickness: Optional[int] = None
    label: Optional[str] = None
    label_arrow: Optional[str] = None  # "<" or ">" taken from the label, see chapter 3.3
    source_cardinality: Optional[str] = None
    target_cardinality: Optional[str] = None
    source_qualifier: Optional[str] = None  # ``Customer [id : UUID] --> Address``
    target_qualifier: Optional[str] = None
    source_member: Optional[str] = None  # ``Class::member --> Other``: the link starts at a member
    target_member: Optional[str] = None
    socket: Optional[str] = None  # "0)", "(0" or "(0)" from ``-0)-``, ``-(0-``, ``-(0)-``
    norank: bool = False  # ``-[norank]->``: layout hint, the link does not influence ranking
    note: Optional["Note"] = None  # ``note on link``
    from_declaration: bool = False  # generated from ``extends`` / ``implements``
    line: int = 0

    @property
    def kind(self) -> RelationKind:
        s, t = self.source_head, self.target_head
        heads = {s, t} - {ArrowHead.NONE}
        dotted = self.line_style is not LineStyle.SOLID
        if self.socket:
            return RelationKind.SOCKET
        if not heads:
            return RelationKind.ASSOCIATION
        if len(heads) == 1:
            head = next(iter(heads))
            if head is ArrowHead.EXTENSION:
                return RelationKind.IMPLEMENTATION if dotted else RelationKind.EXTENSION
            if head is ArrowHead.COMPOSITION:
                return RelationKind.COMPOSITION
            if head is ArrowHead.AGGREGATION:
                return RelationKind.AGGREGATION
            if head is ArrowHead.ARROW:
                return RelationKind.DEPENDENCY if dotted else RelationKind.DIRECTED_ASSOCIATION
            if head is ArrowHead.PLUS:
                return RelationKind.NESTED
            if head is ArrowHead.LOLLIPOP:
                return RelationKind.LOLLIPOP
        return RelationKind.OTHER

    def __repr__(self) -> str:
        left = self.source_head.value
        right = {"<|": "|>", "<": ">", "}": "{"}.get(self.target_head.value, self.target_head.value)
        body = ".." if self.line_style is not LineStyle.SOLID else "--"
        return (
            f"Relationship({_name(self.source)} {left}{body}{right} {_name(self.target)}"
            f"{': ' + self.label if self.label else ''})"
        )


@dataclass(eq=False)
class Note:
    text: str  # raw text; multi-line notes are joined with "\n"
    position: Optional[NotePosition] = None
    target: Union[Entity, Package, Relationship, None] = None  # None for floating notes
    alias: Optional[str] = None  # name of a floating note: ``note "x" as N1``
    member: Optional[str] = None  # ``note right of Class::member``: target is the class
    color: Optional[str] = None
    line: int = 0

    def __repr__(self) -> str:
        return f"Note({self.text[:30]!r}, target={_name(self.target)})"


@dataclass(eq=False)
class NoteLink:
    """Connector between a floating note and an entity: ``Object .. N2``."""

    note: Note
    target: Endpoint
    line_style: LineStyle = LineStyle.DOTTED
    line: int = 0


@dataclass(eq=False)
class AssociationClass:
    """``(Student, Course) .. Enrollment``: ``entity`` is the association class of
    the link between ``first`` and ``second``."""

    first: Entity
    second: Entity
    entity: Entity
    relationship: Optional[Relationship] = None  # the link it hangs on, if one was defined
    line_style: LineStyle = LineStyle.DOTTED
    line: int = 0


@dataclass
class VisibilityRule:
    """One ``hide`` / ``show`` command. Rules are kept in source order because later
    rules override earlier ones."""

    action: RuleAction
    feature: Optional[RuleFeature] = None  # None: hide / show the whole class
    target_kind: RuleTargetKind = RuleTargetKind.ALL
    target: Optional[str] = None  # keyword, stereotype text or qualified entity name
    empty_only: bool = False  # ``hide empty members``
    line: int = 0


@dataclass
class HeaderFooter:
    text: str
    alignment: Optional[str] = None  # "left" | "center" | "right"


@dataclass
class Legend:
    text: str
    horizontal: Optional[str] = None  # "left" | "right" | "center"
    vertical: Optional[str] = None  # "top" | "bottom" | "center"


# ------------------------------------------------------------------------ diagram


@dataclass
class ClassDiagram:
    """Everything found between one ``@startuml`` and ``@enduml``."""

    name: Optional[str] = None  # text after @startuml
    start_line: int = 0
    end_line: Optional[int] = None
    title: Optional[str] = None
    header: Optional[HeaderFooter] = None
    footer: Optional[HeaderFooter] = None
    caption: Optional[str] = None
    legend: Optional[Legend] = None
    direction: LayoutDirection = LayoutDirection.TOP_TO_BOTTOM
    scale: Optional[str] = None  # raw text after ``scale``
    page: Optional[Tuple[int, int]] = None  # ``page 2x2``
    namespace_separator: Optional[str] = "."  # None after ``set namespaceSeparator none``
    allow_mixing: bool = False  # ``allowmixing``: elements of other diagram types are accepted
    skinparams: Dict[str, str] = field(default_factory=dict)
    root: Package = field(default_factory=lambda: Package("", "", PackageKind.ROOT))
    entities: Dict[str, Entity] = field(default_factory=dict)  # by qualified name
    packages: Dict[str, Package] = field(default_factory=dict)  # by qualified name
    relationships: List[Relationship] = field(default_factory=list)
    notes: List[Note] = field(default_factory=list)
    note_links: List[NoteLink] = field(default_factory=list)
    association_classes: List[AssociationClass] = field(default_factory=list)
    rules: List[VisibilityRule] = field(default_factory=list)
    diagnostics: List[Diagnostic] = field(default_factory=list)

    def get_entity(self, name: str) -> Optional[Entity]:
        """Look an entity up by qualified name, or by simple name when that is unambiguous."""
        found = self.entities.get(name)
        if found is not None:
            return found
        matches = [e for e in self.entities.values() if e.name == name]
        return matches[0] if len(matches) == 1 else None

    def get_package(self, name: str) -> Optional[Package]:
        found = self.packages.get(name)
        if found is not None:
            return found
        matches = [p for p in self.packages.values() if p.name == name]
        return matches[0] if len(matches) == 1 else None

    def relationships_of(self, entity: Endpoint) -> List[Relationship]:
        return [r for r in self.relationships if r.source is entity or r.target is entity]

    def entities_of_kind(self, kind: ElementKind) -> List[Entity]:
        return [e for e in self.entities.values() if e.kind is kind]


def _name(obj: object) -> str:
    if obj is None:
        return "None"
    if isinstance(obj, (Entity, Package)):
        return obj.qualified_name
    return type(obj).__name__
