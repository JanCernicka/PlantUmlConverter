"""Command line interface: ``python -m plantuml_converter FILE``."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import List, Optional

from . import CompilationError, compile_file, summarize, to_json

EXIT_OK = 0
EXIT_PROBLEMS = 1  # errors in the input, or no class diagram found
EXIT_USAGE = 2  # file cannot be read, bad arguments

logger = logging.getLogger("plantuml_converter")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plantuml_converter",
        description="Compile a PlantUML class diagram into an object model. "
        "The model is printed to stdout, log messages go to stderr.",
    )
    parser.add_argument("file", help="path to a PlantUML text file")
    parser.add_argument("--format", choices=("summary", "json"), default="summary", help="output format (default: summary)")
    parser.add_argument("--strict", action="store_true", help="fail without output when the input contains errors")
    parser.add_argument("--encoding", help="input file encoding (default: UTF-8, falling back to ISO-8859-1)")
    parser.add_argument(
        "--log-level",
        default="INFO",
        type=str.upper,
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "OFF"),
        help="log level on stderr (default: INFO); DEBUG logs every statement",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    _configure_logging(args.log_level)

    try:
        result = compile_file(args.file, encoding=args.encoding, strict=args.strict)
    except CompilationError as error:
        logger.error("%s", error)
        return EXIT_PROBLEMS
    except (OSError, LookupError, UnicodeDecodeError) as error:
        logger.error("cannot read '%s': %s", args.file, error)
        return EXIT_USAGE

    if args.format == "json":
        print(to_json(result))
    else:
        for diagram in result.diagrams:
            print(summarize(diagram))
        for skipped in result.skipped:
            print(f"Skipped @start{skipped.kind} block at line {skipped.start_line}: {skipped.reason}")
    if not result.diagrams or result.has_errors:
        return EXIT_PROBLEMS
    return EXIT_OK


def _configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"))
    root = logging.getLogger("plantuml_converter")
    root.handlers[:] = [handler]
    root.setLevel(logging.CRITICAL + 1 if level == "OFF" else level)
    root.propagate = False


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
