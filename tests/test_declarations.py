"""Chapter 3.1, 3.8, 3.11, 3.12, 3.15, 3.16, 3.30: declaring elements."""

import pytest

from plantuml_converter import ElementKind, Severity


@pytest.mark.parametrize(
    "line, kind",
    [
        ("class A", ElementKind.CLASS),
        ("abstract A", ElementKind.ABSTRACT_CLASS),
        ("abstract class A", ElementKind.ABSTRACT_CLASS),
        ("annotation A", ElementKind.ANNOTATION),
        ("circle A", ElementKind.CIRCLE),
        ("() A", ElementKind.CIRCLE),
        ("diamond A", ElementKind.DIAMOND),
        ("<> A", ElementKind.DIAMOND),
        ("entity A", ElementKind.ENTITY),
        ("enum A", ElementKind.ENUM),
        ("interface A", ElementKind.INTERFACE),
        ("INTERFACE A", ElementKind.INTERFACE),
    ],
)
def test_every_element_keyword(compile_diagram, line, kind):
    d = compile_diagram(line)
    assert d.entities["A"].kind is kind and not d.entities["A"].implicit


def test_names_equal_to_keywords(compile_diagram):
    # the exact example of chapter 3.1
    d = compile_diagram('abstract abstract\nabstract class "abstract class"\nclass class\nentity entity\nenum enum')
    assert list(d.entities) == ["abstract", "abstract class", "class", "entity", "enum"]
    assert d.entities["abstract"].kind is ElementKind.ABSTRACT_CLASS
    assert d.entities["class"].kind is ElementKind.CLASS
    assert not d.diagnostics


def test_keyword_named_entity_in_relationship(compile_diagram):
    d = compile_diagram("class --> interface\nenum <|-- entity")
    assert list(d.entities) == ["class", "interface", "enum", "entity"]
    assert len(d.relationships) == 2 and all(e.implicit for e in d.entities.values())


def test_alias_with_quoted_label(compile_diagram):
    d = compile_diagram('class "This is my class" as class1\nclass class2 as "It works this way too"\nclass1 --> class2')
    assert d.entities["class1"].display_name == "This is my class"
    assert d.entities["class2"].display_name == "It works this way too"
    assert len(d.relationships) == 1 and len(d.entities) == 2


def test_quoted_name_without_alias(compile_diagram):
    d = compile_diagram('class "Long Name"')
    assert d.entities["Long Name"].name == "Long Name"


def test_generics(compile_diagram):
    d = compile_diagram("class Foo<? extends Element> {\nint size()\n}\nclass Map<K, V<X>> <<Hash>>")
    assert d.entities["Foo"].generics == "? extends Element"
    assert d.entities["Map"].generics == "K, V<X>"
    assert d.entities["Map"].stereotypes == ["Hash"]


def test_stereotypes_and_spot(compile_diagram):
    d = compile_diagram("class Object << general >>\nclass System << (S,#FF7700) Singleton >>\nclass Date << (D,orchid) >>\nclass M <<A>> <<B>>")
    assert d.entities["Object"].stereotypes == ["general"]
    system = d.entities["System"]
    assert (system.spot.character, system.spot.color, system.stereotypes) == ("S", "FF7700", ["Singleton"])
    assert d.entities["Date"].spot.color == "orchid" and d.entities["Date"].stereotypes == []
    assert d.entities["M"].stereotypes == ["A", "B"]


def test_bare_stereotype_line_declares_a_class(compile_diagram):
    d = compile_diagram("Class01 <<Foo>>\nClass01 --> Other")
    assert d.entities["Class01"].stereotypes == ["Foo"] and not d.entities["Class01"].implicit


def test_color(compile_diagram):
    d = compile_diagram("class Foo #red-green\nclass Bar #DDDDDD {\n}\nclass Baz <<S>> #blue")
    assert d.entities["Foo"].color == "red-green"
    assert d.entities["Bar"].color == "DDDDDD"
    assert d.entities["Baz"].color == "blue"


def test_extends_and_implements(compile_diagram):
    d = compile_diagram("class ArrayList implements List\nclass ArrayList extends AbstractList\nclass X extends A, B implements C, D")
    arraylist = d.entities["ArrayList"]
    assert [e.name for e in arraylist.implements] == ["List"]
    assert [e.name for e in arraylist.extends] == ["AbstractList"]
    assert [e.name for e in d.entities["X"].extends] == ["A", "B"]
    assert d.entities["List"].kind is ElementKind.INTERFACE
    rels = [(r.source.name, r.target.name, r.line_style.value, r.from_declaration) for r in d.relationships]
    assert ("List", "ArrayList", "dotted", True) in rels
    assert ("AbstractList", "ArrayList", "solid", True) in rels


def test_brace_on_next_line(compile_diagram):
    d = compile_diagram("class A\n{\n  int x\n}\nclass B")
    assert [m.name for m in d.entities["A"].members] == ["x"] and "B" in d.entities


def test_empty_and_single_line_bodies(compile_diagram):
    d = compile_diagram("class A { }\nclass B { int x }\nclass C {\n}")
    assert d.entities["A"].members == []
    assert [m.name for m in d.entities["B"].members] == ["x"]
    assert not d.diagnostics


def test_unterminated_body_is_an_error_but_members_are_kept(compile_diagram):
    d = compile_diagram("class A {\nint x\n")
    assert [m.name for m in d.entities["A"].members] == ["x"]
    assert [x.severity for x in d.diagnostics] == [Severity.ERROR]


def test_redeclaration_merges(compile_diagram):
    d = compile_diagram("class A {\nint x\n}\nclass A <<S>> {\nint y\n}")
    assert [m.name for m in d.entities["A"].members] == ["x", "y"] and d.entities["A"].stereotypes == ["S"]
    assert not d.diagnostics


def test_redeclaration_with_other_kind_keeps_the_first(compile_diagram):
    d = compile_diagram("class A\ninterface A")
    assert d.entities["A"].kind is ElementKind.CLASS
    assert [x.severity for x in d.diagnostics] == [Severity.WARNING]


def test_declaring_an_implicit_entity_upgrades_it(compile_diagram):
    d = compile_diagram("A --> B\ninterface B")
    assert d.entities["B"].kind is ElementKind.INTERFACE and not d.entities["B"].implicit
    assert d.entities["A"].implicit
    assert len(d.entities) == 2


def test_trailing_garbage_is_a_warning(compile_diagram):
    d = compile_diagram("class A ???")
    assert "A" in d.entities and [x.severity for x in d.diagnostics] == [Severity.WARNING]


def test_unknown_statement_is_an_error_and_compilation_continues(compile_diagram):
    d = compile_diagram("class A\n this is not plantuml \nclass B")
    assert list(d.entities) == ["A", "B"]
    assert [x.severity for x in d.diagnostics] == [Severity.ERROR]


def test_member_added_to_unknown_entity_creates_it(compile_diagram):
    d = compile_diagram("Object : equals()\nObject <|-- ArrayList\nArrayList : Object[] elementData")
    assert d.entities["Object"].implicit
    assert [m.name for m in d.entities["Object"].methods] == ["equals"]
    assert d.entities["ArrayList"].fields[0].type == "Object[]"


@pytest.mark.parametrize(
    "keyword, kind",
    [
        ("exception", ElementKind.EXCEPTION),
        ("struct", ElementKind.STRUCT),
        ("protocol", ElementKind.PROTOCOL),
        ("metaclass", ElementKind.METACLASS),
    ],
)
def test_newer_element_keywords(compile_diagram, keyword, kind):
    d = compile_diagram(f"{keyword} A {{\n  x : int\n}}\nA --> {keyword}")
    assert d.entities["A"].kind is kind and [m.name for m in d.entities["A"].members] == ["x"]
    assert d.entities[keyword].implicit and not d.diagnostics
