import pytest

from plantuml_converter import compile_text


@pytest.fixture
def compile_diagram():
    """Compile the body of a diagram (without @startuml / @enduml) and return the ClassDiagram."""

    def _compile(body: str, **kwargs):
        result = compile_text("@startuml\n" + body + "\n@enduml\n", **kwargs)
        assert len(result.diagrams) == 1, result.skipped
        return result.diagram

    return _compile
