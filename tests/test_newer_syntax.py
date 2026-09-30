"""Syntax beyond chapter 3 of the 1.2020.22 guide that real class diagrams use."""

from plantuml_converter import (
    ArrowHead,
    ElementKind,
    RelationKind,
    RuleAction,
    RuleTargetKind,
    Severity,
    compile_file,
    compile_text,
)
from pathlib import Path

EDGE_CASES = Path(__file__).parent.parent / "examples" / "edge_cases.puml"


def test_stereotype_object_and_map_elements(compile_diagram):
    d = compile_diagram('stereotype Stereo\nobject obj1 {\nname = "x"\nvalue = 42\n}\nmap M {\nkey1 => value1\nkey2 => value2\n}\nclass C')
    assert d.entities["Stereo"].kind is ElementKind.STEREOTYPE
    obj = d.entities["obj1"]
    assert obj.kind is ElementKind.OBJECT and [(m.name, m.default_value) for m in obj.fields] == [("name", '"x"'), ("value", "42")]
    mapping = d.entities["M"]
    assert mapping.kind is ElementKind.MAP and [(m.name, m.default_value) for m in mapping.fields] == [("key1", "value1"), ("key2", "value2")]
    assert not d.diagnostics


def test_object_diagrams_alone_are_still_not_class_diagrams():
    assert not compile_text("@startuml\nobject a\nobject b\na --> b\n@enduml").diagrams


def test_allowmixing_accepts_other_elements():
    d = compile_text("@startuml\nallowmixing\nclass S\ncomponent Comp\nactor Act\ndatabase DB\nusecase UC\nAct --> UC\nS --> Comp\n@enduml").diagram
    assert [e.kind for e in d.entities.values()] == [ElementKind.CLASS, ElementKind.COMPONENT, ElementKind.ACTOR, ElementKind.DATABASE, ElementKind.USECASE]
    assert d.allow_mixing and len(d.relationships) == 2 and not d.diagnostics


def test_other_elements_without_allowmixing_are_errors():
    d = compile_text("@startuml\nclass S\ncomponent Comp\n@enduml").diagram
    assert [x.severity for x in d.diagnostics] == [Severity.ERROR]


def test_allowmixing_does_not_make_a_component_diagram_a_class_diagram():
    assert not compile_text("@startuml\nallowmixing\ncomponent Comp\nclass S\n@enduml").diagrams


def test_enum_constants_with_arguments(compile_diagram):
    d = compile_diagram("enum Planet {\nMERCURY(3.3e+23, 1)\nEARTH\n--\n-mass : double\n}")
    mercury, earth = d.entities["Planet"].fields[:2]
    assert (mercury.name, [p.name for p in mercury.parameters]) == ("MERCURY", ["3.3e+23", "1"])
    assert earth.name == "EARTH" and not d.entities["Planet"].methods


def test_url_and_tags_on_declarations(compile_diagram):
    d = compile_diagram("class A [[https://x.org]]\nclass B [[https://x.org{hover text}]]\nclass C $t1 $t2 <<S>> #red\npackage p [[http://p]] $pt {\n}")
    assert (d.entities["A"].url, d.entities["A"].tooltip) == ("https://x.org", None)
    assert (d.entities["B"].url, d.entities["B"].tooltip) == ("https://x.org", "hover text")
    c = d.entities["C"]
    assert (c.tags, c.stereotypes, c.color) == (["t1", "t2"], ["S"], "red")
    assert (d.packages["p"].url, d.packages["p"].tags) == ("http://p", ["pt"])
    assert not d.diagnostics


def test_sockets(compile_diagram):
    d = compile_diagram("A -0)- B\nC -(0- D\nE -(0)- F")
    assert [r.socket for r in d.relationships] == ["0)", "(0", "(0)"]
    assert all(r.kind is RelationKind.SOCKET and r.source_head is ArrowHead.NONE for r in d.relationships)


def test_norank_and_ports(compile_diagram):
    d = compile_diagram("class A {\nint x\n}\nclass B {\nint y\n}\nA -[norank]-> B\nA::x --> B::y\nA::nothing --> B")
    first, second, third = d.relationships
    assert first.norank and not second.norank
    assert (second.source.name, second.source_member, second.target.name, second.target_member) == ("A", "x", "B", "y")
    assert third.source_member == "nothing" and [x.severity for x in d.diagnostics] == [Severity.WARNING]
    assert set(d.entities) == {"A", "B"}


def test_remove_restore_and_selectors(compile_diagram):
    d = compile_diagram("class A $t\nremove A\nrestore A\nhide $t\nremove $t\nhide @unlinked\nremove @unlinked\nshow <<S>> methods")
    assert [(r.action, r.target_kind, r.target) for r in d.rules][:6] == [
        (RuleAction.REMOVE, RuleTargetKind.ENTITY, "A"),
        (RuleAction.RESTORE, RuleTargetKind.ENTITY, "A"),
        (RuleAction.HIDE, RuleTargetKind.TAG, "t"),
        (RuleAction.REMOVE, RuleTargetKind.TAG, "t"),
        (RuleAction.HIDE, RuleTargetKind.UNLINKED, None),
        (RuleAction.REMOVE, RuleTargetKind.UNLINKED, None),
    ]
    assert not d.diagnostics


def test_anonymous_skinparam_block_and_set_separator(compile_diagram):
    d = compile_diagram("skinparam {\nArrowColor #333333\nclassBorderColor red\n}\nset separator ::\nclass a::B")
    assert d.skinparams == {"ArrowColor": "#333333", "classBorderColor": "red"}
    assert d.namespace_separator == "::" and "a::B" in d.entities


def test_member_parsing_details(compile_diagram):
    d = compile_diagram('class A {\n+fn : (int, int) -> int\n#f(x : int = 5, y : String = "a,b") : void\n}\nA : it\'s fine')
    fn, f, note = d.entities["A"].members
    assert (fn.kind.value, fn.name, fn.type) == ("field", "fn", "(int, int) -> int")
    assert [(p.name, p.type, p.default_value) for p in f.parameters] == [("x", "int", "5"), ("y", "String", '"a,b"')]
    assert note.raw == "it's fine"


def test_empty_cardinality_is_none(compile_diagram):
    d = compile_diagram('A "  " -- " " B')
    assert d.relationships[0].source_cardinality is None and d.relationships[0].target_cardinality is None


def test_edge_case_example_compiles_without_any_diagnostic():
    result = compile_file(EDGE_CASES)
    assert result.all_diagnostics() == [] and not result.skipped
    assert [d.name for d in result.diagrams] == ["edge_cases", "lollipops", "mixing"]
    d = result.diagrams[0]
    # expanded by the preprocessor
    assert d.entities["MacroEntity"].stereotypes == ["Entity"]
    assert [m.name for m in d.entities["GeneratedDto"].fields] == ["payload"]
    assert {"GenClass", "SHOUTING", "ConditionalYes"} <= set(d.entities)
    assert not {"ConditionalNo", "$name", "$prefix"} & set(d.entities)
    # names
    assert d.entities["NWS"].display_name == "Name With Spaces" and d.entities["KeywordName"].display_name == "class"
    assert d.entities["ns1.ns2.Deep"].namespace == "ns1.ns2"
    assert len(d.entities["Dup"].fields) == 2
    assert d.entities["Members"].fields and d.entities["Colored"].color.startswith("pink")
