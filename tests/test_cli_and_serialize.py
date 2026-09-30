import json
import logging
from pathlib import Path

from plantuml_converter import compile_file, compile_text, summarize, to_dict, to_json
from plantuml_converter.cli import EXIT_OK, EXIT_PROBLEMS, EXIT_USAGE, main

SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "sample.plantuml"


def test_sample_compiles_cleanly():
    result = compile_file(SAMPLE)
    assert not result.all_diagnostics()
    diagram = result.diagram
    assert diagram.title == "Order system"
    assert diagram.entities["Payment"].is_abstract


def test_to_dict_is_json_serialisable_and_uses_names_for_references():
    src = (
        "@startuml\nclass A {\n+ run(x : int) : void\n}\nA --> B : uses\nnote right of A : hi\n"
        "package p {\nclass C\n}\n(A, B) .. D\n@enduml"
    )
    data = json.loads(to_json(compile_text(src)))
    diagram = data["diagrams"][0]
    (rel,) = diagram["relationships"]
    assert (rel["source"], rel["target"], rel["kind"], rel["target_head"]) == ("A", "B", "directed association", "arrow")
    assert diagram["notes"][0]["target"] == "A"
    by_name = {e["qualified_name"]: e for e in diagram["entities"]}
    assert by_name["C"]["package"] == "p"
    assert by_name["A"]["members"][0]["parameters"] == [{"name": "x", "type": "int"}]
    assert diagram["association_classes"][0]["entity"] == "D"
    children = diagram["root"]["children"]
    assert {"entity": "A"} in children
    assert next(c for c in children if "name" in c)["children"] == [{"entity": "C"}]


def test_to_dict_accepts_a_single_diagram():
    diagram = compile_text("@startuml\nclass A\n@enduml").diagram
    assert to_dict(diagram)["entities"][0]["name"] == "A"


def test_summary_mentions_entities_and_relationships():
    text = summarize(compile_file(SAMPLE).diagram)
    assert "class Customer" in text and "Payment -extension-> CardPayment" in text


def test_cli_success(capsys):
    assert main([str(SAMPLE), "--log-level", "off"]) == EXIT_OK
    out = capsys.readouterr()
    assert "class Customer" in out.out and out.err == ""


def test_cli_json(capsys):
    assert main([str(SAMPLE), "--format", "json", "--log-level", "off"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["diagrams"][0]["title"] == "Order system"


def test_cli_missing_file(capsys):
    assert main(["/does/not/exist.puml"]) == EXIT_USAGE
    assert "cannot read" in capsys.readouterr().err


def test_cli_directory_instead_of_file(tmp_path):
    assert main([str(tmp_path), "--log-level", "off"]) == EXIT_USAGE


def test_cli_exit_code_for_errors_and_strict(tmp_path, capsys):
    path = tmp_path / "bad.puml"
    path.write_text("@startuml\nclass A\nnonsense\n@enduml")
    assert main([str(path), "--log-level", "off"]) == EXIT_PROBLEMS
    assert "class A" in capsys.readouterr().out  # lenient mode still prints the model
    assert main([str(path), "--strict", "--log-level", "off"]) == EXIT_PROBLEMS
    assert capsys.readouterr().out == ""


def test_cli_no_class_diagram(tmp_path, capsys):
    path = tmp_path / "seq.puml"
    path.write_text("@startuml\nparticipant A\nA -> B\n@enduml")
    assert main([str(path), "--log-level", "off"]) == EXIT_PROBLEMS
    assert "Skipped" in capsys.readouterr().out


def test_cli_bad_encoding_name(tmp_path):
    path = tmp_path / "a.puml"
    path.write_text("@startuml\nclass A\n@enduml")
    assert main([str(path), "--encoding", "nope", "--log-level", "off"]) == EXIT_USAGE


def test_logging_levels(caplog):
    with caplog.at_level(logging.DEBUG, logger="plantuml_converter"):
        compile_text("@startuml\nclass A\nA --> B\nbogus line\n@enduml")
    by_level = {}
    for record in caplog.records:
        by_level.setdefault(record.levelname, []).append(record.getMessage())
    assert any("new class 'A'" in m for m in by_level["DEBUG"])
    assert any("class diagram done" in m for m in by_level["INFO"])
    assert any("bogus line" in m for m in by_level["ERROR"])


def test_library_logs_nothing_above_info_for_clean_input(caplog):
    with caplog.at_level(logging.WARNING, logger="plantuml_converter"):
        compile_file(SAMPLE)
    assert not caplog.records
