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
