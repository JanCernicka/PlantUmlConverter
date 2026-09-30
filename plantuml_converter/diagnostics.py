"""Diagnostics (warnings and errors) collected while compiling PlantUML text."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:  # pragma: no cover
    from .compiler import CompilationResult


class Severity(Enum):
    """WARNING: input was accepted but something was ignored or guessed.
    ERROR: a statement (or a whole block) could not be understood and was dropped."""

    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Diagnostic:
    severity: Severity
    message: str
    line: Optional[int] = None  # 1-based line number in the input text

    def __str__(self) -> str:
        where = f"line {self.line}: " if self.line is not None else ""
        return f"{self.severity.value}: {where}{self.message}"


class PlantUmlError(Exception):
    """Base class of all exceptions raised by this package."""


class CompilationError(PlantUmlError):
    """Raised in strict mode when the input contains errors.

    ``result`` holds everything that was compiled before the error was reported.
    """

    def __init__(self, message: str, result: "CompilationResult") -> None:
        super().__init__(message)
        self.result = result


class Reporter:
    """Collects diagnostics and logs each of them at the matching log level."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self.items: List[Diagnostic] = []

    def warning(self, message: str, line: Optional[int] = None) -> None:
        self._add(Diagnostic(Severity.WARNING, message, line))

    def error(self, message: str, line: Optional[int] = None) -> None:
        self._add(Diagnostic(Severity.ERROR, message, line))

    def _add(self, diagnostic: Diagnostic) -> None:
        self.items.append(diagnostic)
        log = self._logger.warning if diagnostic.severity is Severity.WARNING else self._logger.error
        log("%s", diagnostic)
