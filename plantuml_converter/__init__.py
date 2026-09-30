"""Compiler from PlantUML class diagrams to an object model.

    from plantuml_converter import compile_file

    result = compile_file("diagram.plantuml")
    diagram = result.diagram
    for entity in diagram.entities.values():
        print(entity.kind.value, entity.qualified_name)
"""

import logging

from .compiler import CompilationResult, SkippedBlock, compile_file, compile_text
from .diagnostics import CompilationError, Diagnostic, PlantUmlError, Severity
from .model import *  # noqa: F401,F403 - the model classes are the public result types
from .model import __all__ as _model_names
from .serialize import summarize, to_dict, to_json

# A library must not configure logging for the application, it only offers loggers.
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "compile_text",
    "compile_file",
    "CompilationResult",
    "SkippedBlock",
    "CompilationError",
    "Diagnostic",
    "PlantUmlError",
    "Severity",
    "summarize",
    "to_dict",
    "to_json",
    *_model_names,
]
