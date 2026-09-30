"""Chapter 3.2, 3.3, 3.21 to 3.24, 3.28, 3.31, 3.32: links between classes."""

import pytest

from plantuml_converter import ArrowHead, Direction, LineStyle, RelationKind, Severity


def only(diagram):
    (rel,) = diagram.relationships
    return rel


@pytest.mark.parametrize(
    "text, left, right, style, kind",
    [
        ("A <|-- B", ArrowHead.EXTENSION, ArrowHead.NONE, LineStyle.SOLID, RelationKind.EXTENSION),
        ("A <|.. B", ArrowHead.EXTENSION, ArrowHead.NONE, LineStyle.DOTTED, RelationKind.IMPLEMENTATION),
        ("A ..|> B", ArrowHead.NONE, ArrowHead.EXTENSION, LineStyle.DOTTED, RelationKind.IMPLEMENTATION),
        ("A *-- B", ArrowHead.COMPOSITION, ArrowHead.NONE, LineStyle.SOLID, RelationKind.COMPOSITION),
        ("A o-- B", ArrowHead.AGGREGATION, ArrowHead.NONE, LineStyle.SOLID, RelationKind.AGGREGATION),
        ("A .. B", ArrowHead.NONE, ArrowHead.NONE, LineStyle.DOTTED, RelationKind.ASSOCIATION),
        ("A -- B", ArrowHead.NONE, ArrowHead.NONE, LineStyle.SOLID, RelationKind.ASSOCIATION),
        ("A --> B", ArrowHead.NONE, ArrowHead.ARROW, LineStyle.SOLID, RelationKind.DIRECTED_ASSOCIATION),
        ("A ..> B", ArrowHead.NONE, ArrowHead.ARROW, LineStyle.DOTTED, RelationKind.DEPENDENCY),
        ("A <-- B", ArrowHead.ARROW, ArrowHead.NONE, LineStyle.SOLID, RelationKind.DIRECTED_ASSOCIATION),
        ("A <--* B", ArrowHead.ARROW, ArrowHead.COMPOSITION, LineStyle.SOLID, RelationKind.OTHER),
        ("A #-- B", ArrowHead.HASH, ArrowHead.NONE, LineStyle.SOLID, RelationKind.OTHER),
        ("A x-- B", ArrowHead.CROSS, ArrowHead.NONE, LineStyle.SOLID, RelationKind.OTHER),
        ("A }-- B", ArrowHead.CROWFOOT, ArrowHead.NONE, LineStyle.SOLID, RelationKind.OTHER),
        ("A +-- B", ArrowHead.PLUS, ArrowHead.NONE, LineStyle.SOLID, RelationKind.NESTED),
        ("A ^-- B", ArrowHead.CARET, ArrowHead.NONE, LineStyle.SOLID, RelationKind.OTHER),
        ("A -o B", ArrowHead.NONE, ArrowHead.AGGREGATION, LineStyle.SOLID, RelationKind.AGGREGATION),
        ("A --* B", ArrowHead.NONE, ArrowHead.COMPOSITION, LineStyle.SOLID, RelationKind.COMPOSITION),
        ("bar ()- A", ArrowHead.LOLLIPOP, ArrowHead.NONE, LineStyle.SOLID, RelationKind.LOLLIPOP),
        ("A -() bar", ArrowHead.NONE, ArrowHead.LOLLIPOP, LineStyle.SOLID, RelationKind.LOLLIPOP),
    ],
)
def test_arrow_types(compile_diagram, text, left, right, style, kind):
    rel = only(compile_diagram(text))
    assert (rel.source_head, rel.target_head, rel.line_style, rel.kind) == (left, right, style, kind)


def test_arrows_without_spaces(compile_diagram):
    d = compile_diagram("A-->B\nC..>D\nE<|--F\nG--*H")
    assert [(r.source.name, r.target.name) for r in d.relationships] == [("A", "B"), ("C", "D"), ("E", "F"), ("G", "H")]


def test_operands_keep_source_order(compile_diagram):
    rel = only(compile_diagram("Class19 <--* Class20"))
    assert (rel.source.name, rel.target.name) == ("Class19", "Class20")


def test_entities_are_created_implicitly_in_order(compile_diagram):
    d = compile_diagram("A --> B\nB --> C")
    assert list(d.entities) == ["A", "B", "C"] and all(e.implicit for e in d.entities.values())
    assert d.relationships[0].target is d.relationships[1].source


def test_label_and_cardinality(compile_diagram):
    rel = only(compile_diagram('Class01 "1" *-- "many" Class02 : contains'))
    assert (rel.source_cardinality, rel.target_cardinality, rel.label) == ("1", "many", "contains")
    rel = only(compile_diagram('A --> "1" B'))
    assert (rel.source_cardinality, rel.target_cardinality, rel.label) == (None, "1", None)
    rel = only(compile_diagram('A "0..*" - "1..*" B'))
    assert (rel.source_cardinality, rel.target_cardinality) == ("0..*", "1..*")


def test_label_may_contain_colons_and_arrows_in_text(compile_diagram):
    rel = only(compile_diagram("A --> B : url: http://x and a -> b"))
    assert rel.label == "url: http://x and a -> b"


def test_label_without_space_before_colon(compile_diagram):
    assert only(compile_diagram("A --> B: hello")).label == "hello"


def test_label_direction_arrow(compile_diagram):
    d = compile_diagram("Driver - Car : drives >\nCar *- Wheel : have 4 >\nCar -- Person : < owns")
    assert [(r.label, r.label_arrow) for r in d.relationships] == [("drives", ">"), ("have 4", ">"), ("owns", "<")]


def test_label_with_html_is_not_mistaken_for_a_direction(compile_diagram):
    assert only(compile_diagram("A --> B : <b>bold</b>")).label_arrow is None


def test_quoted_name_that_is_not_a_cardinality(compile_diagram):
    d = compile_diagram('class class2\nclass2 *-- "foo/dummy" : use')
    rel = only(d)
    assert rel.target.name == "foo/dummy" and rel.target_cardinality is None and rel.label == "use"


def test_quoted_operands_with_spaces(compile_diagram):
    d = compile_diagram('"Big Class" --> "Other Class" : x')
    assert list(d.entities) == ["Big Class", "Other Class"]


def test_direction_keywords(compile_diagram):
    d = compile_diagram("a -left-> b\na -right-> c\na -up-> d\na -down-> e\na -d-> f\na -do-> g\na -l-> h")
    assert [r.direction for r in d.relationships] == [
        Direction.LEFT, Direction.RIGHT, Direction.UP, Direction.DOWN, Direction.DOWN, Direction.DOWN, Direction.LEFT,
    ]


def test_arrow_length(compile_diagram):
    d = compile_diagram("a - b\na -- c\na --- d")
    assert [r.length for r in d.relationships] == [1, 2, 3]


def test_inline_style(compile_diagram):
    d = compile_diagram(
        "a -[bold]-> b\na -[dashed]-> c\na -[dotted]-> d\na -[hidden]-> e\na -[plain]-> f\n"
        "a -[#red]-> g\na -[#blue,bold,thickness=3]-> h\nBar1 -[hidden]> Bar2"
    )
    r = d.relationships
    assert r[0].bold and r[1].line_style is LineStyle.DASHED and r[2].line_style is LineStyle.DOTTED
    assert r[3].hidden and r[4].line_style is LineStyle.SOLID
    assert r[5].color == "red"
    assert (r[6].color, r[6].bold, r[6].thickness) == ("blue", True, 3)
    assert r[7].hidden and r[7].target_head is ArrowHead.ARROW and r[7].length == 1


def test_plain_overrides_dotted_body(compile_diagram):
    assert only(compile_diagram("a .[plain]. b")).line_style is LineStyle.SOLID


def test_new_style_notation(compile_diagram):
    d = compile_diagram(
        "foo --> bar1 #line:red;line.bold;text:red : red bold\nfoo --> bar2 #green;line.dashed;text:green : green dashed\nfoo --> bar3 #blue"
    )
    a, b, c = d.relationships
    assert (a.color, a.text_color, a.bold, a.label) == ("red", "red", True, "red bold")
    assert (b.color, b.text_color, b.line_style, b.label) == ("green", "green", LineStyle.DASHED, "green dashed")
    assert c.color == "blue"


def test_unknown_inline_style_is_a_warning(compile_diagram):
    d = compile_diagram("a -[wobbly]-> b")
    assert len(d.relationships) == 1 and [x.severity for x in d.diagnostics] == [Severity.WARNING]


def test_self_relationship(compile_diagram):
    rel = only(compile_diagram("Node --> Node : child"))
    assert rel.source is rel.target


def test_namespace_separator_chars_in_names(compile_diagram):
    d = compile_diagram("java.util.List <|-- java.util.ArrayList")
    assert list(d.entities) == ["java.util.List", "java.util.ArrayList"]
    assert d.entities["java.util.List"].namespace == "java.util" and d.entities["java.util.List"].name == "List"


def test_incomplete_relationship_is_a_syntax_error(compile_diagram):
    d = compile_diagram("A -->\nB --")
    assert [x.severity for x in d.diagnostics] == [Severity.ERROR, Severity.ERROR]
    assert not d.relationships and not d.entities


def test_relationships_of_helper(compile_diagram):
    d = compile_diagram("A --> B\nB --> C\nC --> A")
    assert len(d.relationships_of(d.entities["A"])) == 2


def test_association_class(compile_diagram):
    d = compile_diagram('class Student\nStudent "0..*" - "1..*" Course\n(Student, Course) .. Enrollment\nclass Enrollment {\ndrop()\n}')
    (assoc,) = d.association_classes
    assert (assoc.first.name, assoc.second.name, assoc.entity.name) == ("Student", "Course", "Enrollment")
    assert assoc.relationship is d.relationships[0]
    assert len(d.relationships) == 1 and d.entities["Enrollment"].methods


def test_association_class_other_direction_and_reversed_operands(compile_diagram):
    d = compile_diagram("Course -- Student\nEnrollment . (Student, Course)")
    (assoc,) = d.association_classes
    assert assoc.relationship is d.relationships[0] and assoc.entity.name == "Enrollment"


def test_association_class_without_link_warns(compile_diagram):
    d = compile_diagram("(A, B) .. C")
    assert d.association_classes[0].relationship is None
    assert [x.severity for x in d.diagnostics] == [Severity.WARNING]


def test_association_on_same_class_with_diamond(compile_diagram):
    d = compile_diagram('class Station\nclass StationCrossing\n<> diamond\nStationCrossing . diamond\ndiamond - "from 0..*" Station\ndiamond - "to 0..* " Station')
    assert d.entities["diamond"].kind.value == "diamond"
    assert [(r.source.name, r.target.name, r.target_cardinality) for r in d.relationships][1:] == [
        ("diamond", "Station", "from 0..*"),
        ("diamond", "Station", "to 0..*"),
    ]


def test_qualifiers(compile_diagram):
    d = compile_diagram('Customer [addressId : UUID] --> Address : lookup\nA "1" [k] -- [j] "*" B')
    first, second = d.relationships
    assert (first.source_qualifier, first.target_qualifier, first.label) == ("addressId : UUID", None, "lookup")
    assert (second.source_cardinality, second.source_qualifier, second.target_qualifier, second.target_cardinality) == ("1", "k", "j", "*")


def test_direction_keyword_after_inline_style(compile_diagram):
    d = compile_diagram("a -[hidden]right- b\na -[#red]down-> c\na -left[bold]-> d")
    first, second, third = d.relationships
    assert (first.hidden, first.direction) == (True, Direction.RIGHT)
    assert (second.color, second.direction, second.target_head) == ("red", Direction.DOWN, ArrowHead.ARROW)
    assert (third.bold, third.direction) == (True, Direction.LEFT)
