"""Chapter 3.8 to 3.10, 3.13, 3.14, 3.25 to 3.29 and the common commands."""

from plantuml_converter import (
    LayoutDirection,
    NotePosition,
    RuleAction,
    RuleFeature,
    RuleTargetKind,
    Severity,
)


def test_note_of_entity_single_line(compile_diagram):
    d = compile_diagram("class Object << general >>\nnote top of Object : In java, every class\\nextends this one.")
    (note,) = d.notes
    assert note.target is d.entities["Object"] and note.position is NotePosition.TOP
    assert note.text == "In java, every class\\nextends this one."


def test_note_of_entity_multi_line_with_color(compile_diagram):
    d = compile_diagram("class Foo\nnote left of Foo #blue\\9932CC\nthis is my\nnote on this class\nend note")
    (note,) = d.notes
    assert note.text == "this is my\nnote on this class" and note.color == "blue\\9932CC"


def test_note_on_last_defined_class(compile_diagram):
    d = compile_diagram("class A\nclass B\nnote left: On last defined class")
    assert d.notes[0].target is d.entities["B"] and d.notes[0].position is NotePosition.LEFT


def test_note_on_last_class_multi_line(compile_diagram):
    d = compile_diagram("class A\nnote right\nline 1\n\nline 3\nendnote")
    assert d.notes[0].text == "line 1\n\nline 3"


def test_note_on_entity_created_by_relationship(compile_diagram):
    d = compile_diagram("A --> B\nnote bottom: about B")
    assert d.notes[0].target is d.entities["B"]


def test_floating_notes_and_note_links(compile_diagram):
    d = compile_diagram(
        'class Object\nclass ArrayList\nnote "This is a floating note" as N1\nnote "connected\\nto several" as N2\n'
        "Object .. N2\nN2 .. ArrayList"
    )
    assert [n.alias for n in d.notes] == ["N1", "N2"] and d.notes[0].target is None
    assert [(l.note.alias, l.target.name) for l in d.note_links] == [("N2", "Object"), ("N2", "ArrayList")]
    assert not d.relationships and set(d.entities) == {"Object", "ArrayList"}


def test_multi_line_floating_note(compile_diagram):
    d = compile_diagram("note as N1\nThis note is <u>also</u>\non several lines\nend note\nclass A\nA .. N1")
    assert d.notes[0].text == "This note is <u>also</u>\non several lines" and d.note_links[0].target.name == "A"


def test_note_on_link(compile_diagram):
    d = compile_diagram(
        "Dummy --> Foo : A link\nnote on link #red: note that is red\nDummy --> Foo2 : Another link\n"
        "note right on link #blue\nthis is my note on right link\nand in blue\nend note"
    )
    first, second = d.relationships
    assert first.note.text == "note that is red" and first.note.color == "red" and first.note.target is first
    assert second.note.position is NotePosition.RIGHT and second.note.text.endswith("and in blue")
    assert len(d.notes) == 2


def test_note_problems(compile_diagram):
    d = compile_diagram("note left: nobody\nnote on link: nothing\nclass A\nnote left of B\nnever closed")
    assert [x.severity for x in d.diagnostics] == [Severity.ERROR, Severity.ERROR, Severity.ERROR]
    assert d.notes[0].text.startswith("never closed") or len(d.notes) == 1


def test_hide_show_rules(compile_diagram):
    d = compile_diagram(
        "class Dummy1\nclass Dummy3 <<Serializable>>\nclass Foo2\nhide members\nhide <<Serializable>> circle\nshow Dummy1 methods\n"
        "hide empty members\nhide interface methods\nhide Foo2\nshow class fields\nhide empty attributes\nhide stereotype"
    )
    rules = d.rules
    assert (rules[0].action, rules[0].feature, rules[0].target_kind) == (RuleAction.HIDE, RuleFeature.MEMBERS, RuleTargetKind.ALL)
    assert (rules[1].feature, rules[1].target_kind, rules[1].target) == (RuleFeature.CIRCLE, RuleTargetKind.STEREOTYPE, "Serializable")
    assert (rules[2].action, rules[2].target_kind, rules[2].target) == (RuleAction.SHOW, RuleTargetKind.ENTITY, "Dummy1")
    assert rules[3].empty_only and rules[3].feature is RuleFeature.MEMBERS
    assert (rules[4].target_kind, rules[4].target) == (RuleTargetKind.ELEMENT_KIND, "interface")
    assert (rules[5].feature, rules[5].target_kind, rules[5].target) == (None, RuleTargetKind.ENTITY, "Foo2")
    assert rules[6].target == "class" and rules[6].feature is RuleFeature.FIELDS
    assert rules[7].feature is RuleFeature.FIELDS and rules[7].empty_only
    assert rules[8].feature is RuleFeature.STEREOTYPE
    assert not d.diagnostics


def test_hide_unknown_class_warns(compile_diagram):
    d = compile_diagram("hide Nothing")
    assert [x.severity for x in d.diagnostics] == [Severity.WARNING]


def test_skinparam(compile_diagram):
    d = compile_diagram(
        "skinparam classAttributeIconSize 0\nskinparam class {\nBackgroundColor PaleGreen\nArrowColor SeaGreen\n"
        "BackgroundColor<<Foo>> Wheat\n}\nskinparam stereotypeCBackgroundColor<< Foo >> DimGray\nskinparam backgroundcolor AntiqueWhite/Gold"
    )
    assert d.skinparams == {
        "classAttributeIconSize": "0",
        "classBackgroundColor": "PaleGreen",
        "classArrowColor": "SeaGreen",
        "classBackgroundColor<<Foo>>": "Wheat",
        "stereotypeCBackgroundColor<<Foo>>": "DimGray",
        "backgroundcolor": "AntiqueWhite/Gold",
    }


def test_skinparam_problems(compile_diagram):
    d = compile_diagram("skinparam lonely\nskinparam class {\nBackgroundColor Red")
    assert [x.severity for x in d.diagnostics] == [Severity.WARNING, Severity.ERROR]
    assert d.skinparams == {"classBackgroundColor": "Red"}


def test_title_header_footer_caption_legend(compile_diagram):
    d = compile_diagram(
        "title Simple\\nexample\nheader some header\ncenter footer Generated\ncaption figure 1\n"
        "legend top left\nShort\nlegend\nendlegend"
    )
    assert d.title == "Simple\\nexample" and d.header.text == "some header" and d.header.alignment is None
    assert (d.footer.text, d.footer.alignment) == ("Generated", "center")
    assert d.caption == "figure 1"
    assert (d.legend.text, d.legend.horizontal, d.legend.vertical) == ("Short\nlegend", "left", "top")


def test_multi_line_title_and_header(compile_diagram):
    d = compile_diagram("title\n<u>Simple</u> communication\non several lines\nend title\nheader\nWarning:\nDo not use.\nendheader\nclass A")
    assert d.title == "<u>Simple</u> communication\non several lines"
    assert d.header.text == "Warning:\nDo not use."
    assert "A" in d.entities


def test_layout_commands(compile_diagram):
    d = compile_diagram("left to right direction\nscale 200*100\npage 2x2")
    assert d.direction is LayoutDirection.LEFT_TO_RIGHT and d.scale == "200*100" and d.page == (2, 2)
    assert compile_diagram("class A").direction is LayoutDirection.TOP_TO_BOTTOM


def test_unsupported_but_valid_commands_warn(compile_diagram):
    d = compile_diagram("newpage\nallowmixing\nclass A")
    assert [x.severity for x in d.diagnostics] == [Severity.WARNING, Severity.WARNING] and "A" in d.entities


def test_entity_named_like_a_command_word(compile_diagram):
    d = compile_diagram("set --> hide\nscale --> show\nhide <|-- show")
    assert [(r.source.name, r.target.name) for r in d.relationships] == [("set", "hide"), ("scale", "show"), ("hide", "show")]


def test_note_on_member(compile_diagram):
    d = compile_diagram("class EventBus {\n+publish(e : Event)\n}\nnote right of EventBus::publish\nSynchronous.\nend note")
    (note,) = d.notes
    assert note.target is d.entities["EventBus"] and note.member == "publish" and not d.diagnostics
    assert set(d.entities) == {"EventBus"}


def test_note_on_unknown_member_warns_but_keeps_the_note(compile_diagram):
    d = compile_diagram("class A\nnote left of A::nothing : x")
    assert d.notes[0].member == "nothing" and [x.severity for x in d.diagnostics] == [Severity.WARNING]


def test_together_lists_existing_entities_without_moving_them(compile_diagram):
    d = compile_diagram("package p {\nclass A\nclass B\n}\ntogether {\nclass A\nclass C\n}")
    group = next(g for g in d.packages.values() if g.kind.value == "together")
    assert [e.name for e in group.iter_entities()] == ["A", "C"]
    assert d.entities["A"].package is d.packages["p"]
