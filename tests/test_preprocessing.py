"""Comments, line endings, encodings."""

import logging

from plantuml_converter import compile_file, compile_text


def test_line_comments(compile_diagram):
    d = compile_diagram("' a comment\nclass A\n   ' indented comment\nclass B")
    assert list(d.entities) == ["A", "B"]


def test_block_comments(compile_diagram):
    d = compile_diagram("/' one line '/ class A\n/'\nclass Hidden\n'/\nclass B /' trailing '/")
    assert list(d.entities) == ["A", "B"]
    assert not d.diagnostics


def test_enduml_inside_block_comment_does_not_end_the_diagram():
    result = compile_text("@startuml\n/'\n@enduml\n'/\nclass A\n@enduml")
    assert list(result.diagram.entities) == ["A"]


def test_apostrophe_inside_text_is_not_a_comment(compile_diagram):
    d = compile_diagram("class A\nA : it's here\nA --> B : don't")
    assert d.entities["A"].members[0].raw == "it's here"
    assert d.relationships[0].label == "don't"


def test_comment_markers_inside_quotes_are_kept(compile_diagram):
    d = compile_diagram('class "a /\' b" as A')
    assert d.entities["A"].display_name == "a /' b"


def test_windows_and_old_mac_line_endings():
    for newline in ("\r\n", "\r"):
        result = compile_text(newline.join(["@startuml", "class A", "A --> B", "@enduml"]))
        assert list(result.diagram.entities) == ["A", "B"]
        assert result.diagram.relationships[0].line == 3


def test_tabs_and_surrounding_whitespace(compile_diagram):
    d = compile_diagram("\t class\tA  \n   A\t-->\tB\t")
    assert len(d.relationships) == 1


def test_utf8_bom_and_unicode_names(tmp_path):
    path = tmp_path / "d.puml"
    path.write_bytes("﻿@startuml\nclass Zákazník\nZákazník --> Objednávka\n@enduml".encode("utf-8"))
    assert list(compile_file(path).diagram.entities) == ["Zákazník", "Objednávka"]


def test_non_utf8_file_falls_back_with_warning(tmp_path, caplog):
    path = tmp_path / "d.puml"
    path.write_bytes("@startuml\nclass \"caf\xe9\" as A\n@enduml".encode("latin-1"))
    with caplog.at_level(logging.WARNING, logger="plantuml_converter"):
        result = compile_file(path)
    assert result.diagram.entities["A"].display_name == "café"
    assert "ISO-8859-1" in caplog.text


def test_explicit_encoding(tmp_path):
    path = tmp_path / "d.puml"
    path.write_bytes("@startuml\nclass \"žluť\" as A\n@enduml".encode("cp1250"))
    assert compile_file(path, encoding="cp1250").diagram.entities["A"].display_name == "žluť"


def test_include_directive_is_a_warning_not_an_error(compile_diagram):
    d = compile_diagram("!include common.puml\n!pragma layout smetana\nclass A")
    assert [x.severity.value for x in d.diagnostics] == ["warning"]
