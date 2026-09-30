"""Public entry points: ``compile_text`` and ``compile_file``."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional, Union

from .detector import detect
from .diagnostics import CompilationError, Diagnostic, Reporter, Severity
from .model import ClassDiagram
from .macros import Preprocessor
from .parser import ClassDiagramParser
from .preprocessor import split_blocks

logger = logging.getLogger(__name__)


@dataclass
class SkippedBlock:
    """A block of the input that was not compiled because it is not a class diagram."""

    kind: str  # "uml" or another @start keyword such as "mindmap"
    start_line: int
    reason: str


@dataclass
class CompilationResult:
    diagrams: List[ClassDiagram] = field(default_factory=list)
    skipped: List[SkippedBlock] = field(default_factory=list)
    diagnostics: List[Diagnostic] = field(default_factory=list)  # problems outside of any diagram

    @property
    def diagram(self) -> Optional[ClassDiagram]:
        """The first class diagram, or ``None`` when the input has none."""
        return self.diagrams[0] if self.diagrams else None

    def all_diagnostics(self) -> List[Diagnostic]:
        found = list(self.diagnostics)
        for diagram in self.diagrams:
            found.extend(diagram.diagnostics)
        return found

    @property
    def has_errors(self) -> bool:
        return any(d.severity is Severity.ERROR for d in self.all_diagnostics())


def compile_text(text: str, *, strict: bool = False) -> CompilationResult:
    """Compile PlantUML text into class diagram models.

    Only ``@startuml`` blocks that contain a class diagram are compiled; everything
    else is listed in ``result.skipped``. Problems never abort the compilation
    unless ``strict`` is true, in which case ``CompilationError`` is raised after
    the whole text was processed if any error was reported.
    """
    result = CompilationResult()
    reporter = Reporter(logger)
    blocks = split_blocks(text, reporter)
    result.diagnostics = reporter.items

    for block in blocks:
        if block.kind != "uml":
            reason = f"@start{block.kind} is not a class diagram"
            logger.info("line %d: skipping block: %s", block.start_line, reason)
            result.skipped.append(SkippedBlock(block.kind, block.start_line, reason))
            continue

        # Macros change what the statements are, so they are expanded before detection. The
        # diagnostics stay silent unless the block really is a class diagram.
        block_reporter = Reporter(logger, buffered=True)
        block.lines = Preprocessor(block_reporter).run(block.lines)

        detection = detect(block.lines)
        if not detection.is_class_diagram:
            logger.info("line %d: skipping @startuml block: %s", block.start_line, detection.reason)
            result.skipped.append(SkippedBlock(block.kind, block.start_line, detection.reason))
            continue

        logger.info("line %d: compiling class diagram (%s)", block.start_line, detection.reason)
        block_reporter.flush()
        diagram = ClassDiagramParser(block, block_reporter).parse()
        if not any(line.text for line in block.lines):
            block_reporter.warning("diagram is empty", block.start_line)
            diagram.diagnostics = list(block_reporter.items)
        logger.info(
            "line %d: class diagram done: %d entities, %d relationships, %d notes, %d problem(s)",
            block.start_line,
            len(diagram.entities),
            len(diagram.relationships),
            len(diagram.notes),
            len(diagram.diagnostics),
        )
        result.diagrams.append(diagram)

    if not result.diagrams:
        logger.warning("no class diagram found in the input")
    if strict and result.has_errors:
        errors = [d for d in result.all_diagnostics() if d.severity is Severity.ERROR]
        raise CompilationError(f"{len(errors)} error(s) in input, first: {errors[0]}", result)
    return result


def compile_file(path: Union[str, "os.PathLike[str]"], *, encoding: Optional[str] = None, strict: bool = False) -> CompilationResult:
    """Read ``path`` and compile it.

    Without ``encoding`` the file is decoded as UTF-8 (a BOM is accepted, like
    PlantUML does). If that fails, ISO-8859-1 is used and a warning is logged, so
    a file in a legacy encoding still compiles.
    """
    logger.info("reading '%s'", os.fspath(path))
    with open(path, "rb") as handle:
        data = handle.read()

    if encoding:
        text = data.decode(encoding)
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            logger.warning("'%s' is not valid UTF-8, decoding it as ISO-8859-1", os.fspath(path))
            text = data.decode("latin-1")
    logger.debug("read %d characters", len(text))
    return compile_text(text, strict=strict)
