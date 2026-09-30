"""All examples of chapter 3 (class diagram) of the PlantUML Language Reference Guide 1.2020.22."""

import random
from pathlib import Path

import pytest

from plantuml_converter import compile_file, compile_text

GUIDE = Path(__file__).parent / "data" / "reference_guide_chapter3.plantuml"


def test_all_guide_examples_compile_without_any_diagnostic():
    result = compile_file(GUIDE)
    assert len(result.diagrams) == 46 and not result.skipped
    assert result.all_diagnostics() == []


def test_chapter_3_1_declares_eleven_elements():
    first = compile_file(GUIDE).diagrams[0]
    assert len(first.entities) == 11 and len(first.relationships) == 0


@pytest.mark.parametrize("seed", range(20))
def test_damaged_input_never_crashes(seed):
    """Delete, duplicate and swap characters and lines of the guide: the compiler must not raise."""
    rng = random.Random(seed)
    lines = GUIDE.read_text().split("\n")
    for _ in range(rng.randint(5, 60)):
        i = rng.randrange(len(lines))
        action = rng.choice(["drop", "dup", "cut", "insert"])
        if action == "drop":
            del lines[i]
        elif action == "dup":
            lines.insert(i, lines[i])
        elif action == "cut" and lines[i]:
            j = rng.randrange(len(lines[i]))
            lines[i] = lines[i][:j] + lines[i][j + rng.randint(1, 5) :]
        else:
            lines.insert(i, rng.choice(['"', "{", "}", "<<", ">>", "(A,", "note left of", "--", "class", "#", "'/", "/'", "@startuml", "@enduml"]))
        if not lines:
            lines = [""]
    result = compile_text("\n".join(lines))
    result.all_diagnostics()


def test_ecommerce_example_compiles_without_any_diagnostic():
    example = Path(__file__).parent.parent / "examples" / "ecommerce_architecture.puml"
    result = compile_file(example)
    assert result.all_diagnostics() == []
    diagram = result.diagram
    assert len(diagram.entities) == 64
    assert {e.name for e in diagram.entities.values() if e.implicit} == {"RuntimeException", "Refundable"}
    assert [m.name for m in diagram.entities["Dimensions"].fields] == ["width", "height", "depth"]


def test_design_patterns_example_compiles_without_any_diagnostic():
    example = Path(__file__).parent.parent / "examples" / "design_patterns.puml"
    result = compile_file(example)
    assert result.all_diagnostics() == [] and not result.skipped
    observer, strategy, composite, domain = result.diagrams
    assert [d.name for d in result.diagrams] == ["Observer", "Strategy and Factory", "Composite and Decorator", "Domain model"]

    subject = observer.entities["AbstractSubject"]
    assert subject.generics == "T" and [e.name for e in subject.implements] == ["Subject"]
    assert observer.notes[0].target is observer.entities["Thermostat"]

    registry = strategy.entities["Registry"]
    assert registry.spot.character == "S" and registry.stereotypes == ["Singleton"]
    assert [m.name for m in registry.members if getattr(m, "is_static", False)] == ["instance", "getInstance"]
    assert strategy.entities["CardPayment"].package is strategy.packages["com.acme.payment"]

    group = next(p for p in composite.packages.values() if p.kind.value == "together")
    assert [e.name for e in group.iter_entities()] == ["BoldDecorator", "ColorDecorator"]

    assert domain.entities["library.model.Book"].namespace == "library.model"
    assert domain.association_classes[0].entity.name == "Loan"
    assert domain.notes[0].target.target.name == "Audited"  # the note sits on the last link
