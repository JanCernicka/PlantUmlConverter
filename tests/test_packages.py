"""Chapter 3.17 to 3.20, 3.28: packages, namespaces, together."""

from plantuml_converter import PackageKind, Severity


def test_packages_nest_and_hold_entities(compile_diagram):
    d = compile_diagram('package "Classic Collections" #DDDDDD {\nObject <|-- ArrayList\n}\npackage net.sourceforge.plantuml {\nObject <|-- Demo1\nDemo1 *- Demo2\n}')
    classic = d.packages["Classic Collections"]
    assert classic.color == "DDDDDD" and classic.kind is PackageKind.PACKAGE
    assert [e.name for e in classic.iter_entities()] == ["Object", "ArrayList"]
    assert [e.name for e in d.packages["net.sourceforge.plantuml"].iter_entities()] == ["Demo1", "Demo2"]
    assert d.entities["ArrayList"].package is classic
    # in packages the simple name is the identity: Object exists once
    assert len([e for e in d.entities.values() if e.name == "Object"]) == 1


def test_nested_packages(compile_diagram):
    d = compile_diagram("package outer {\npackage inner {\nclass A\n}\nclass B\n}")
    outer, inner = d.packages["outer"], d.packages["outer.inner"]
    assert inner in outer.children and d.entities["A"].package is inner and d.entities["B"].package is outer
    assert d.root.children == [outer]


def test_package_stereotype_and_style(compile_diagram):
    d = compile_diagram("package foo1 <<Node>> {\nclass Class1\n}\npackage foo2 <<Rectangle>> {\n}")
    assert d.packages["foo1"].stereotypes == ["Node"] and d.packages["foo2"].stereotypes == ["Rectangle"]


def test_package_alias_and_brace_on_next_line(compile_diagram):
    d = compile_diagram('package p as "Long name"\n{\nclass A\n}')
    assert d.packages["p"].display_name == "Long name" and d.entities["A"].package is d.packages["p"]


def test_reopening_a_package(compile_diagram):
    d = compile_diagram("package p {\nclass A\n}\npackage p {\nclass B\n}")
    assert len(d.packages) == 1 and [e.name for e in d.packages["p"].iter_entities()] == ["A", "B"]


def test_empty_package_on_one_line(compile_diagram):
    d = compile_diagram("package p { }\nclass A")
    assert d.entities["A"].package is d.root and not d.diagnostics


def test_links_between_packages(compile_diagram):
    d = compile_diagram("package foo1.foo2 {\n}\npackage foo1.foo2.foo3 {\nclass Object\n}\nfoo1.foo2 +-- foo1.foo2.foo3")
    rel = d.relationships[0]
    assert rel.source is d.packages["foo1.foo2"] and rel.target is d.packages["foo1.foo2.foo3"]
    assert set(d.entities) == {"Object"}


def test_namespaces_qualify_names(compile_diagram):
    # the example of chapter 3.19
    d = compile_diagram(
        "class BaseClass\nnamespace net.dummy #DDDDDD {\n.BaseClass <|-- Person\nMeeting o-- Person\n.BaseClass <|- Meeting\n}\n"
        "namespace net.foo {\nnet.dummy.Person <|- Person\n.BaseClass <|-- Person\nnet.dummy.Meeting o-- Person\n}\n"
        "BaseClass <|-- net.unused.Person"
    )
    assert set(d.entities) == {"BaseClass", "net.dummy.Person", "net.dummy.Meeting", "net.foo.Person", "net.unused.Person"}
    assert d.packages["net.dummy"].kind is PackageKind.NAMESPACE and d.packages["net.dummy"].color == "DDDDDD"
    assert d.entities["net.foo.Person"].package is d.packages["net.foo"]
    # the automatically created namespace
    assert d.packages["net.unused"].kind is PackageKind.NAMESPACE
    assert d.entities["net.unused.Person"].package is d.packages["net.unused"]
    sources = {(r.source.qualified_name, r.target.qualified_name) for r in d.relationships}
    assert ("BaseClass", "net.foo.Person") in sources and ("net.dummy.Person", "net.foo.Person") in sources
    assert d.entities["BaseClass"].namespace is None


def test_same_simple_name_in_two_namespaces(compile_diagram):
    d = compile_diagram("namespace a {\nclass X\n}\nnamespace b {\nclass X\n}")
    assert set(d.entities) == {"a.X", "b.X"}


def test_nested_namespaces(compile_diagram):
    d = compile_diagram("namespace a {\nnamespace b {\nclass X\n}\n}")
    assert "a.b.X" in d.entities and d.packages["a.b"].kind is PackageKind.NAMESPACE


def test_custom_namespace_separator(compile_diagram):
    d = compile_diagram("set namespaceSeparator ::\nclass X1::X2::foo {\nsome info\n}")
    foo = d.entities["X1::X2::foo"]
    assert foo.name == "foo" and foo.namespace == "X1::X2" and d.namespace_separator == "::"
    assert d.packages["X1::X2"].kind is PackageKind.NAMESPACE


def test_namespace_separator_none(compile_diagram):
    d = compile_diagram("set namespaceSeparator none\nclass X1.X2.foo")
    assert d.entities["X1.X2.foo"].namespace is None and d.namespace_separator is None and not d.packages


def test_quoted_names_are_not_split(compile_diagram):
    d = compile_diagram('class "a.b" as c\n"v1.0" --> c')
    assert set(d.entities) == {"c", "v1.0"} and not d.packages


def test_together(compile_diagram):
    d = compile_diagram("class Bar1\ntogether {\nclass Together1\nclass Together2\n}\nTogether1 - Together2")
    group = next(p for p in d.packages.values() if p.kind is PackageKind.TOGETHER)
    assert [e.name for e in group.iter_entities()] == ["Together1", "Together2"]
    assert d.entities["Bar1"].package is d.root


def test_unclosed_package_is_an_error(compile_diagram):
    d = compile_diagram("package p {\nclass A")
    assert "A" in d.entities and [x.severity for x in d.diagnostics] == [Severity.ERROR]


def test_unmatched_closing_brace_is_an_error(compile_diagram):
    d = compile_diagram("class A\n}\nclass B")
    assert list(d.entities) == ["A", "B"] and [x.severity for x in d.diagnostics] == [Severity.ERROR]


def test_package_without_brace_is_an_error(compile_diagram):
    d = compile_diagram("package p\nclass A")
    assert "A" in d.entities and d.diagnostics[0].severity is Severity.ERROR


def test_implicit_entity_declared_later_inside_a_package_moves_there(compile_diagram):
    d = compile_diagram("A --> B\npackage p {\nclass B\n}")
    assert d.entities["B"].package is d.packages["p"]
    assert d.entities["B"] not in d.root.children
