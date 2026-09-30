"""Splitting the input into diagrams and deciding which ones are class diagrams."""

import pytest

from plantuml_converter import CompilationError, Severity, compile_text


def test_text_outside_blocks_is_ignored():
    result = compile_text("hello\n@startuml\nclass A\n@enduml\nbye\n")
    assert list(result.diagram.entities) == ["A"]
    assert not result.all_diagnostics()


def test_name_after_startuml():
    assert compile_text('@startuml "My Project"\nclass A\n@enduml').diagram.name == "My Project"
    assert compile_text("@startuml foo.png\nclass A\n@enduml").diagram.name == "foo.png"


def test_keywords_are_case_insensitive():
    result = compile_text("@STARTUML\nCLASS A\n@ENDUML")
    assert "A" in result.diagram.entities


def test_several_diagrams_in_one_file():
    text = "@startuml\nclass A\n@enduml\n\n@startuml\nclass B\n@enduml\n"
    result = compile_text(text)
    assert [list(d.entities) for d in result.diagrams] == [["A"], ["B"]]
    assert result.diagrams[1].start_line == 5


def test_line_numbers_are_relative_to_the_whole_file():
    result = compile_text("\n\n@startuml\nclass A\nthis is nonsense\n@enduml")
    (diagnostic,) = result.all_diagnostics()
    assert diagnostic.line == 5 and diagnostic.severity is Severity.ERROR


@pytest.mark.parametrize("kind", ["mindmap", "json", "gantt", "salt", "wbs", "yaml"])
def test_other_start_keywords_are_skipped(kind):
    result = compile_text(f"@start{kind}\n* root\n** child\n@end{kind}\n@startuml\nclass A\n@enduml")
    assert [s.kind for s in result.skipped] == [kind]
    assert len(result.diagrams) == 1


@pytest.mark.parametrize(
    "body",
    [
        "participant Alice\nAlice -> Bob : hi",
        "Alice ->> Bob : hi",
        "start\n:Hello;\nstop",
        "[*] --> Idle\nIdle --> [*]",
        "state Idle",
        "component Foo\n[Foo] --> Bar",
        "usecase UC1\nactor User",
        "(Use case) --> (Other)",
        "object Foo",
        "node n\n(u) -> [c]",
        "salt\n{\nLogin\n}",
        "note over Alice : hi",
    ],
)
def test_other_uml_diagram_types_are_skipped(body):
    result = compile_text(f"@startuml\n{body}\n@enduml")
    assert not result.diagrams
    assert len(result.skipped) == 1 and result.skipped[0].kind == "uml"


@pytest.mark.parametrize(
    "body",
    [
        "a -- b",  # the reference guide itself shows this as a class diagram
        "Foo --> Bar",
        "class A",
        "interface Foo\nFoo <|-- Bar",
        "Object : equals()\nObject <|-- ArrayList",  # 'Object' is a class name here, not the keyword
        "Node o-- Leaf",
        "package foo {\nclass A\n}",
        "skinparam shadowing false",
    ],
)
def test_class_diagrams_are_accepted(body):
    result = compile_text(f"@startuml\n{body}\n@enduml")
    assert len(result.diagrams) == 1, result.skipped


def test_first_marker_decides_not_later_lines():
    result = compile_text("@startuml\nclass A\ncomponent B\n@enduml")
    assert len(result.diagrams) == 1
    assert any("component B" in d.message for d in result.diagram.diagnostics)


def test_note_text_is_not_inspected_for_markers():
    body = "note as N\nparticipant in text\nend note\nclass A"
    assert len(compile_text(f"@startuml\n{body}\n@enduml").diagrams) == 1


def test_class_body_is_not_inspected_for_markers():
    body = "interface I {\nstate\n}\nclass A"
    assert len(compile_text(f"@startuml\n{body}\n@enduml").diagrams) == 1


def test_empty_input_and_empty_diagram():
    result = compile_text("")
    assert not result.diagrams and not result.skipped
    result = compile_text("@startuml\n@enduml")
    assert len(result.diagrams) == 1
    assert [d.severity for d in result.diagram.diagnostics] == [Severity.WARNING]


def test_missing_enduml_is_an_error_but_the_diagram_is_still_compiled():
    result = compile_text("@startuml\nclass A")
    assert "A" in result.diagram.entities
    assert result.has_errors
    assert result.diagram.end_line is None


def test_new_startuml_inside_open_block_starts_a_new_diagram():
    result = compile_text("@startuml\nclass A\n@startuml\nclass B\n@enduml")
    assert [list(d.entities) for d in result.diagrams] == [["A"], ["B"]]
    assert result.has_errors


def test_enduml_without_start_is_a_warning():
    result = compile_text("@enduml\n@startuml\nclass A\n@enduml")
    assert [d.severity for d in result.diagnostics] == [Severity.WARNING]


def test_no_class_diagram_at_all():
    result = compile_text("@startmindmap\n* a\n@endmindmap")
    assert result.diagram is None and len(result.skipped) == 1


def test_strict_mode_raises_after_processing_everything():
    with pytest.raises(CompilationError) as info:
        compile_text("@startuml\nclass A\nnonsense here\n@enduml", strict=True)
    assert "A" in info.value.result.diagram.entities


def test_strict_mode_accepts_warnings():
    compile_text("@startuml\n!include foo.puml\nclass A\n@enduml", strict=True)
