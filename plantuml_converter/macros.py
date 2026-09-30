"""Preprocessor of chapter 20 of the language reference.

Runs on the statements of one ``@startuml`` block before the diagram type is detected and
before parsing. It supports

* variables:            ``!$x = "a" + 1``, ``!global`` / ``!local``, ``$x`` in the text
* conditions, loops:    ``!if`` / ``!elseif`` / ``!else`` / ``!endif``, ``!ifdef``, ``!ifndef``, ``!while``
* procedures:           ``!procedure`` / ``!endprocedure`` (also ``!unquoted``, default and keyword arguments)
* return functions:     ``!function`` / ``!return`` / ``!endfunction`` (also one-line form)
* legacy macros:        ``!define NAME body``, ``!define NAME(args) body``, ``!definelong``, ``!undef``
* builtin functions:    ``%true() %false() %not() %upper() %lower() %strlen() %strpos() %substr()
                        %string() %intval() %newline() %version() %variable_exists() %function_exists()
                        %get_variable_value() %set_variable_value()``
* ``##`` argument concatenation, ``!assert``, ``!log``, ``!dump_memory``

Not supported (reported as warnings, the directive is dropped): ``!include*``, ``!import``,
``!includesub``, ``!theme``. Builtins that depend on the environment (``%date``, ``%getenv``,
``%filename``, ``%dirpath``, ``%file_exists``) are left unevaluated in the text.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

from .diagnostics import Reporter
from .preprocessor import LogicalLine

logger = logging.getLogger(__name__)

Value = Union[int, str]

MAX_CALL_DEPTH = 50
MAX_LOOP_ITERATIONS = 1000
MAX_OUTPUT_LINES = 50_000
MAX_STEPS = 50_000  # statements executed, guards against exponential recursion
MAX_CALLS = 10_000

_ASSIGN = re.compile(r"^!(?:(?P<scope>global|local)\s+)?(?P<name>[$A-Za-z_]\w*)\s*(?P<cond>\?)?=(?!=)\s*(?P<expr>.*)$")
_DIRECTIVE = re.compile(r"^!(?P<name>[A-Za-z_]\w*)\b\s*(?P<rest>.*)$")
_CALLABLE_HEAD = re.compile(r"^!(?:(?P<unq>unquoted)\s+)?(?P<kind>function|procedure)\s+(?P<name>\$?\w+)\s*\(")
_DEFINE = re.compile(r"^!(?P<kind>define|definelong)\s+(?P<name>\w+)(?P<params>\([^)]*\))?\s*(?P<body>.*)$")
_CALL_LINE = re.compile(r"^(?P<name>\$?[A-Za-z_]\w*)\s*\(")
_IDENT = re.compile(r"[^\W\d]\w*")  # unicode letters are allowed in names
_VAR = re.compile(r"\$[A-Za-z_]\w*")
_TOKEN = re.compile(
    r"""\s*(?:
        (?P<num>\d+)
      | (?P<str>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
      | (?P<call>[$%]?[A-Za-z_]\w*)\s*\(
      | (?P<var>\$[A-Za-z_]\w*)
      | (?P<name>[A-Za-z_]\w*)
      | (?P<op>==|!=|<=|>=|&&|\|\||[-+*/<>!(),=])
    )""",
    re.VERBOSE,
)


class _Stop(Exception):
    """Internal: abort preprocessing (runaway expansion)."""


@dataclass
class _Callable:
    name: str
    params: List[Tuple[str, Optional[str]]]  # (parameter name, default expression)
    body: List[LogicalLine]
    is_function: bool
    unquoted: bool = False


@dataclass
class _Macro:
    """Legacy ``!define``: plain text replacement."""

    name: str
    params: Optional[List[str]]
    body: str


@dataclass
class _Frame:
    variables: Dict[str, Value] = field(default_factory=dict)
    words: Dict[str, str] = field(default_factory=dict)  # parameters written without '$'
    is_global: bool = False
    returned: Optional[Value] = None
    done: bool = False


class Preprocessor:
    def __init__(self, reporter: Reporter) -> None:
        self._rep = reporter
        self._globals: Dict[str, Value] = {}
        self._macros: Dict[str, _Macro] = {}
        self._callables: Dict[str, _Callable] = {}
        self._out: List[LogicalLine] = []
        self._depth = 0
        self._steps = 0
        self._calls = 0

    # ------------------------------------------------------------------ driver

    def run(self, lines: List[LogicalLine]) -> List[LogicalLine]:
        if not any(line.text.startswith("!") or "$" in line.text or "%" in line.text for line in lines):
            return lines  # nothing to do, keep the statements as they are
        top = _Frame(variables=self._globals, is_global=True)
        try:
            self._exec(lines, top, None)
        except _Stop:
            pass
        except Exception as error:  # a bug here must not lose the whole diagram
            logger.exception("preprocessor failed")
            self._rep.error(f"preprocessor failed ({error!r}), macros were not expanded", lines[0].number if lines else None)
            return lines
        logger.debug("preprocessor: %d statement(s) became %d", len(lines), len(self._out))
        return self._out

    def _exec(self, lines: List[LogicalLine], frame: _Frame, site: Optional[int]) -> None:
        i = 0
        while i < len(lines) and not frame.done:
            self._steps += 1
            if self._steps > MAX_STEPS:
                self._rep.error(f"preprocessing needs more than {MAX_STEPS} steps (runaway recursion?), stopped", lines[i].number)
                raise _Stop
            line = lines[i]
            if line.text.startswith("!"):
                i = self._directive(lines, i, frame, site)
            else:
                self._text_line(line, frame, site)
                i += 1

    def _emit(self, text: str, number: int) -> None:
        if len(self._out) >= MAX_OUTPUT_LINES:
            self._rep.error(f"preprocessing produced more than {MAX_OUTPUT_LINES} lines, stopped", number)
            raise _Stop
        self._out.append(LogicalLine(number, text))

    # -------------------------------------------------------------- text lines

    def _text_line(self, line: LogicalLine, frame: _Frame, site: Optional[int]) -> None:
        number = site or line.number
        text = line.text
        if not text:
            self._emit(text, number)
            return

        call = _CALL_LINE.match(text)
        if call:
            target = self._callables.get(call.group("name"))
            if target is not None and not target.is_function:
                args_end = _matching_paren(text, call.end() - 1)
                if args_end == len(text) - 1:
                    self._call(target, text[call.end() : args_end], frame, number, discard_output=False)
                    return

        expanded = self._expand(text, frame, number)
        for part in expanded.split("\n"):
            self._emit(part, number)

    def _expand(self, text: str, frame: _Frame, number: int) -> str:
        """Replace ``$var``, ``$function(...)``, ``%builtin(...)``, define macros and parameter words."""
        if not any(c in text for c in "$%") and not (self._macros or self._callables or frame.words):
            return text
        out: List[str] = []
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch in "$%":
                m = re.compile(r"[$%][A-Za-z_]\w*").match(text, i)
                if m:
                    name = m.group()
                    after = m.end()
                    function = self._callables.get(name)
                    if after < n and text[after] == "(" and (name[0] == "%" or (function and function.is_function)):
                        end = _matching_paren(text, after)
                        if end > 0:
                            value = self._call_named(name, text[after + 1 : end], frame, number, in_text=True)
                            if value is None:  # environment dependent builtin: keep as written
                                out.append(text[i : end + 1])
                            else:
                                out.append(str(value))
                            i = end + 1
                            continue
                    if name[0] == "$":
                        value = self._lookup(name, frame)
                        if value is not None:
                            out.append(str(value))
                            i = after
                            continue
                    out.append(name)
                    i = after
                    continue
            elif ch.isalpha() or ch == "_":
                m = _IDENT.match(text, i)
                if m is None:
                    out.append(ch)
                    i += 1
                    continue
                word = m.group()
                after = m.end()
                before_ok = i == 0 or not (text[i - 1].isalnum() or text[i - 1] in "_$")
                if before_ok and word in frame.words:
                    out.append(frame.words[word])
                    i = after
                    continue
                function = self._callables.get(word) if before_ok else None
                if function is not None and function.is_function and after < n and text[after] == "(":
                    end = _matching_paren(text, after)
                    if end > 0:  # function written without '$', see !unquoted
                        out.append(str(self._call(function, text[after + 1 : end], frame, number, discard_output=True)))
                        i = end + 1
                        continue
                macro = self._macros.get(word) if before_ok else None
                if macro is not None:
                    if macro.params is None:
                        out.append(self._expand(macro.body, frame, number))
                        i = after
                        continue
                    if after < n and text[after] == "(":
                        end = _matching_paren(text, after)
                        if end > 0:
                            args = [a.strip() for a in _split_args(text[after + 1 : end])]
                            out.append(self._expand(_apply_macro(macro, args), frame, number))
                            i = end + 1
                            continue
                out.append(word)
                i = after
                continue
            out.append(ch)
            i += 1
        return re.sub(r"(?<=\w)##(?=\w)", "", "".join(out))

    # -------------------------------------------------------------- directives

    def _directive(self, lines: List[LogicalLine], i: int, frame: _Frame, site: Optional[int]) -> int:
        line = lines[i]
        text = line.text
        number = site or line.number

        assign = _ASSIGN.match(text)
        if assign and assign.group("name") not in _DIRECTIVE_WORDS:
            self._assign(assign, frame, number)
            return i + 1

        head = _CALLABLE_HEAD.match(text)
        if head:
            return self._define_callable(lines, i, head)

        m = _DIRECTIVE.match(text)
        if not m:
            self._rep.warning(f"preprocessor directive is not supported and was ignored: {text!r}", number)
            return i + 1
        name, rest = m.group("name").lower(), m.group("rest").strip()

        if name in ("if", "ifdef", "ifndef"):
            return self._conditional(lines, i, frame, site)
        if name == "while":
            return self._while(lines, i, frame, site)
        if name in ("define", "definelong"):
            return self._define(lines, i, name)
        if name == "undef":
            self._macros.pop(rest, None)
            self._globals.pop(rest, None)
        elif name == "return":
            frame.returned = self._eval(rest, frame, number)
            frame.done = True
        elif name == "assert":
            expr, _, message = rest.partition(" : ")
            if not _truthy(self._eval(expr, frame, number)):
                self._rep.error(f"assertion failed: {expr.strip()} {message.strip()}".strip(), number)
        elif name in ("log", "dump_memory", "memory_dump"):
            logger.debug("line %d: %s %s", number, name, rest)
        elif name == "pragma":
            logger.debug("line %d: pragma ignored: %s", number, text)
        elif name in ("startsub", "endsub"):
            logger.debug("line %d: %s ignored", number, name)
        elif name in ("else", "elseif", "endif", "endwhile", "endfunction", "endprocedure", "enddefinelong"):
            self._rep.error(f"'!{name}' without matching opening directive", number)
        else:
            self._rep.warning(f"preprocessor directive is not supported and was ignored: {text!r}", number)
        return i + 1

    def _assign(self, m: "re.Match[str]", frame: _Frame, number: int) -> None:
        name = m.group("name")
        if m.group("cond") and self._lookup(name, frame) is not None:
            return
        value = self._eval(m.group("expr"), frame, number)
        scope = m.group("scope")
        if scope == "global" or frame.is_global:
            self._globals[name] = value
        elif scope == "local" or name not in self._globals:
            frame.variables[name] = value
        else:
            self._globals[name] = value
        logger.debug("line %d: %s = %r", number, name, value)

    def _conditional(self, lines: List[LogicalLine], i: int, frame: _Frame, site: Optional[int]) -> int:
        """``!if`` ... ``!elseif`` ... ``!else`` ... ``!endif``; returns the index after ``!endif``."""
        branches: List[Tuple[str, str, int]] = []  # (kind, condition text, index of the directive)
        depth = 0
        j = i
        end = len(lines)
        while j < len(lines):
            m = _DIRECTIVE.match(lines[j].text)
            word = m.group("name").lower() if m else ""
            if word in ("if", "ifdef", "ifndef"):
                if depth == 0:
                    branches.append((word, m.group("rest").strip(), j))  # type: ignore[union-attr]
                depth += 1
            elif word in ("elseif", "else") and depth == 1:
                branches.append((word, m.group("rest").strip(), j))  # type: ignore[union-attr]
            elif word == "endif":
                depth -= 1
                if depth == 0:
                    end = j
                    break
            j += 1
        else:
            self._rep.error("'!if' is never closed with '!endif'", lines[i].number)

        bounds = [b[2] for b in branches] + [end]
        for index, (kind, condition, start) in enumerate(branches):
            number = site or lines[start].number
            if kind == "else":
                taken = True
            elif kind == "ifdef":
                taken = self._is_defined(condition)
            elif kind == "ifndef":
                taken = not self._is_defined(condition)
            else:
                taken = _truthy(self._eval(condition, frame, number))
            if taken:
                self._exec(lines[start + 1 : bounds[index + 1]], frame, site)
                break
        return end + 1

    def _while(self, lines: List[LogicalLine], i: int, frame: _Frame, site: Optional[int]) -> int:
        condition = _DIRECTIVE.match(lines[i].text).group("rest")  # type: ignore[union-attr]
        depth = 0
        end = len(lines)
        for j in range(i, len(lines)):
            m = _DIRECTIVE.match(lines[j].text)
            word = m.group("name").lower() if m else ""
            if word == "while":
                depth += 1
            elif word == "endwhile":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        else:
            self._rep.error("'!while' is never closed with '!endwhile'", lines[i].number)
        body = lines[i + 1 : end]
        number = site or lines[i].number
        for _ in range(MAX_LOOP_ITERATIONS):
            if frame.done or not _truthy(self._eval(condition, frame, number)):
                break
            self._exec(body, frame, site)
        else:
            self._rep.error(f"'!while' stopped after {MAX_LOOP_ITERATIONS} iterations", number)
        return end + 1

    def _define_callable(self, lines: List[LogicalLine], i: int, head: "re.Match[str]") -> int:
        line = lines[i]
        is_function = head.group("kind") == "function"
        open_idx = head.end() - 1
        close_idx = _matching_paren(line.text, open_idx)
        if close_idx < 0:
            self._rep.error(f"unbalanced parentheses in definition: {line.text!r}", line.number)
            return i + 1
        params = _parse_params(line.text[open_idx + 1 : close_idx])
        trailing = line.text[close_idx + 1 :].strip()
        end_word = "endfunction" if is_function else "endprocedure"

        if trailing:  # one-line form: !function $double($a) !return $a + $a
            body = [LogicalLine(line.number, trailing)]
            next_index = i + 1
        else:
            j = i + 1
            while j < len(lines) and not re.match(rf"^!{end_word}\b", lines[j].text, re.IGNORECASE):
                j += 1
            if j >= len(lines):
                self._rep.error(f"'{head.group('name')}' is never closed with '!{end_word}'", line.number)
            body = lines[i + 1 : j]
            next_index = j + 1
        name = head.group("name")
        self._callables[name] = _Callable(name, params, body, is_function, bool(head.group("unq")))
        logger.debug("line %d: %s '%s' defined", line.number, head.group("kind"), name)
        return next_index

    def _define(self, lines: List[LogicalLine], i: int, kind: str) -> int:
        line = lines[i]
        m = _DEFINE.match(line.text)
        if not m:
            self._rep.warning(f"cannot parse {line.text!r}", line.number)
            return i + 1
        name = m.group("name")
        params = m.group("params")
        names = [p.strip() for p in params[1:-1].split(",") if p.strip()] if params else None
        if kind == "definelong":
            j = i + 1
            while j < len(lines) and not re.match(r"^!enddefinelong\b", lines[j].text, re.IGNORECASE):
                j += 1
            if j >= len(lines):
                self._rep.error(f"'{name}' is never closed with '!enddefinelong'", line.number)
            self._callables[name] = _Callable(name, [(p, None) for p in names or []], lines[i + 1 : j], False, True)
            return j + 1
        self._macros[name] = _Macro(name, names, m.group("body").strip())
        logger.debug("line %d: macro '%s' defined", line.number, name)
        return i + 1

    def _is_defined(self, name: str) -> bool:
        return name in self._macros or name in self._globals or name in self._callables

    # ------------------------------------------------------------------- calls

    def _call_named(self, name: str, arg_text: str, frame: _Frame, number: int, in_text: bool = False) -> Optional[Value]:
        target = self._callables.get(name)
        if target is not None:
            return self._call(target, arg_text, frame, number, discard_output=True)
        args = [self._eval(a, frame, number) for a in _split_args(arg_text) if a.strip()]
        return self._builtin(name.lower(), args, frame, number)

    def _call(self, target: _Callable, arg_text: str, caller: _Frame, number: int, discard_output: bool) -> Value:
        if self._depth >= MAX_CALL_DEPTH:
            self._rep.error(f"call of '{target.name}' is nested deeper than {MAX_CALL_DEPTH} levels", number)
            return ""
        self._calls += 1
        if self._calls > MAX_CALLS:
            self._rep.error(f"more than {MAX_CALLS} calls while preprocessing (runaway recursion?), stopped", number)
            raise _Stop
        positional: List[Value] = []
        keywords: Dict[str, Value] = {}
        for raw in _split_args(arg_text):
            if not raw.strip():
                continue
            key = re.match(r"^\s*(\$?[A-Za-z_]\w*)\s*=(?!=)\s*(.*)$", raw, re.DOTALL)
            if key and any(key.group(1) == p[0] for p in target.params):
                keywords[key.group(1)] = self._argument(target, key.group(2), caller, number)
            else:
                positional.append(self._argument(target, raw, caller, number))

        frame = _Frame()
        for index, (pname, default) in enumerate(target.params):
            if index < len(positional):
                value: Value = positional[index]
            elif pname in keywords:
                value = keywords[pname]
            elif default is not None:
                value = self._eval(default, frame, number)
            else:
                self._rep.error(f"'{target.name}' called without its argument '{pname}'", number)
                value = ""
            if pname.startswith("$"):
                frame.variables[pname] = value
            else:
                frame.words[pname] = str(value)
        if len(positional) > len(target.params):
            self._rep.warning(f"'{target.name}' called with too many arguments", number)

        self._depth += 1
        saved = self._out
        if discard_output:
            self._out = []
        try:
            self._exec(target.body, frame, number)
        finally:
            self._depth -= 1
            self._out = saved
        return frame.returned if frame.returned is not None else ""

    def _argument(self, target: _Callable, raw: str, frame: _Frame, number: int) -> Value:
        raw = raw.strip()
        if target.unquoted and not re.match(r"""^(?:"|'|\d+$|\$|%)""", raw):
            return self._expand(raw, frame, number)
        return self._eval(raw, frame, number)

    def _builtin(self, name: str, args: List[Value], frame: _Frame, number: int) -> Optional[Value]:
        def text(i: int) -> str:
            return str(args[i]) if i < len(args) else ""

        try:
            if name == "%true":
                return 1
            if name == "%false":
                return 0
            if name == "%not":
                return 0 if _truthy(args[0]) else 1
            if name == "%upper":
                return text(0).upper()
            if name == "%lower":
                return text(0).lower()
            if name == "%strlen":
                return len(text(0))
            if name == "%string":
                return text(0)
            if name == "%intval":
                return int(text(0))
            if name == "%newline":
                return "\\n"
            if name == "%version":
                return "1.2020.22"
            if name == "%strpos":
                return text(0).find(text(1))
            if name == "%substr":
                start = int(args[1])
                return text(0)[start : start + int(args[2])] if len(args) > 2 else text(0)[start:]
            if name == "%variable_exists":
                return 1 if self._lookup(text(0), frame) is not None else 0
            if name == "%function_exists":
                return 1 if text(0) in self._callables else 0
            if name == "%get_variable_value":
                value = self._lookup(text(0), frame)
                return "" if value is None else value
            if name == "%set_variable_value":
                self._globals[text(0)] = args[1] if len(args) > 1 else ""
                return ""
            if name in ("%date", "%getenv", "%filename", "%dirpath", "%file_exists"):
                return None
        except (ValueError, IndexError):
            self._rep.error(f"invalid arguments for {name}()", number)
            return ""
        self._rep.warning(f"unknown function '{name}' ignored", number)
        return None

    # ------------------------------------------------------------- expressions

    def _lookup(self, name: str, frame: _Frame) -> Optional[Value]:
        if name in frame.variables:
            return frame.variables[name]
        return self._globals.get(name)

    def _eval(self, text: str, frame: _Frame, number: int) -> Value:
        tokens = _tokenize(text)
        if tokens is None:
            self._rep.error(f"cannot evaluate expression {text.strip()!r}", number)
            return ""
        parser = _ExprParser(self, tokens, frame, number)
        try:
            value = parser.parse()
        except ValueError as error:
            self._rep.error(f"cannot evaluate expression {text.strip()!r}: {error}", number)
            return ""
        return value


# --------------------------------------------------------------- expression parser

_DIRECTIVE_WORDS = {"if", "ifdef", "ifndef", "elseif", "else", "endif", "while", "endwhile", "return", "assert", "log"}


def _tokenize(text: str) -> Optional[List[Tuple[str, str]]]:
    tokens: List[Tuple[str, str]] = []
    pos = 0
    text = text.rstrip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            return None
        kind = m.lastgroup or ""
        tokens.append((kind, m.group(kind)))
        pos = m.end()
    return tokens


class _ExprParser:
    """Recursive descent: ``||`` < ``&&`` < ``== !=`` < ``< <= > >=`` < ``+ -`` < ``* /`` < unary."""

    def __init__(self, owner: Preprocessor, tokens: List[Tuple[str, str]], frame: _Frame, number: int) -> None:
        self._owner, self._tokens, self._frame, self._number = owner, tokens, frame, number
        self._pos = 0

    def parse(self) -> Value:
        if not self._tokens:
            return ""
        value = self._or()
        if self._pos != len(self._tokens):
            raise ValueError(f"unexpected {self._tokens[self._pos][1]!r}")
        return value

    def _peek_op(self, *ops: str) -> Optional[str]:
        if self._pos < len(self._tokens):
            kind, text = self._tokens[self._pos]
            if kind == "op" and text in ops:
                return text
        return None

    def _take(self) -> Tuple[str, str]:
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def _or(self) -> Value:
        value = self._and()
        while self._peek_op("||"):
            self._take()
            right = self._and()
            value = 1 if _truthy(value) or _truthy(right) else 0
        return value

    def _and(self) -> Value:
        value = self._equality()
        while self._peek_op("&&"):
            self._take()
            right = self._equality()
            value = 1 if _truthy(value) and _truthy(right) else 0
        return value

    def _equality(self) -> Value:
        value = self._relational()
        while True:
            op = self._peek_op("==", "!=")
            if not op:
                return value
            self._take()
            right = self._relational()
            same = str(value) == str(right)
            value = 1 if same == (op == "==") else 0

    def _relational(self) -> Value:
        value = self._additive()
        while True:
            op = self._peek_op("<", "<=", ">", ">=")
            if not op:
                return value
            self._take()
            right = self._additive()
            a, b = (value, right) if isinstance(value, int) and isinstance(right, int) else (str(value), str(right))
            value = int({"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op])  # type: ignore[operator]

    def _additive(self) -> Value:
        value = self._multiplicative()
        while True:
            op = self._peek_op("+", "-")
            if not op:
                return value
            self._take()
            right = self._multiplicative()
            if op == "+":
                value = value + right if isinstance(value, int) and isinstance(right, int) else f"{value}{right}"
            else:
                value = _as_int(value) - _as_int(right)

    def _multiplicative(self) -> Value:
        value = self._unary()
        while True:
            op = self._peek_op("*", "/")
            if not op:
                return value
            self._take()
            right = _as_int(self._unary())
            if op == "*":
                value = _as_int(value) * right
            else:
                if right == 0:
                    raise ValueError("division by zero")
                value = _as_int(value) // right

    def _unary(self) -> Value:
        if self._peek_op("!"):
            self._take()
            return 0 if _truthy(self._unary()) else 1
        if self._peek_op("-"):
            self._take()
            return -_as_int(self._unary())
        return self._primary()

    def _primary(self) -> Value:
        if self._pos >= len(self._tokens):
            raise ValueError("unexpected end")
        kind, text = self._take()
        if kind == "num":
            return int(text)
        if kind == "str":
            return _unescape(text[1:-1])
        if kind == "var":
            value = self._owner._lookup(text, self._frame)
            if value is None:
                self._owner._rep.error(f"variable {text} is not defined", self._number)
                return ""
            return value
        if kind == "name":
            return text
        if kind == "call":
            args = self._arguments()
            target = self._owner._callables.get(text)
            if target is not None:
                return self._owner._call(target, args, self._frame, self._number, discard_output=True)
            evaluated = [self._owner._eval(a, self._frame, self._number) for a in _split_args(args) if a.strip()]
            result = self._owner._builtin(text.lower(), evaluated, self._frame, self._number)
            return "" if result is None else result
        if kind == "op" and text == "(":
            value = self._or()
            if not self._peek_op(")"):
                raise ValueError("missing ')'")
            self._take()
            return value
        raise ValueError(f"unexpected {text!r}")

    def _arguments(self) -> str:
        """Raw text of the arguments of a call whose '(' was just consumed."""
        depth = 1
        start = self._pos
        while self._pos < len(self._tokens):
            kind, text = self._tokens[self._pos]
            if kind == "call" or (kind == "op" and text == "("):
                depth += 1
            elif kind == "op" and text == ")":
                depth -= 1
                if depth == 0:
                    raw = self._tokens[start : self._pos]
                    self._pos += 1
                    return " ".join(_untokenize(t) for t in raw)
            self._pos += 1
        raise ValueError("missing ')'")


def _untokenize(token: Tuple[str, str]) -> str:
    kind, text = token
    return text + "(" if kind == "call" else text


# ------------------------------------------------------------------------ helpers


def _truthy(value: Value) -> bool:
    return value != 0 and value != ""


def _as_int(value: Value) -> int:
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{value!r} is not a number") from None


def _unescape(text: str) -> str:
    return text.replace('\\"', '"').replace("\\'", "'")


def _matching_paren(text: str, open_idx: int) -> int:
    """Index of the ')' matching the '(' at ``open_idx``, ignoring quoted text; -1 if none."""
    depth = 0
    quote = ""
    for i in range(open_idx, len(text)):
        ch = text[i]
        if quote:
            if ch == quote and text[i - 1] != "\\":
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _split_args(text: str) -> List[str]:
    """Split call arguments at top-level commas, ignoring commas in quotes and parentheses."""
    parts: List[str] = []
    depth = 0
    quote = ""
    start = 0
    for i, ch in enumerate(text):
        if quote:
            if ch == quote and text[i - 1] != "\\":
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return parts


def _parse_params(text: str) -> List[Tuple[str, Optional[str]]]:
    params: List[Tuple[str, Optional[str]]] = []
    for raw in _split_args(text):
        raw = raw.strip()
        if not raw:
            continue
        name, eq, default = raw.partition("=")
        params.append((name.strip(), default.strip() if eq else None))
    return params


def _apply_macro(macro: _Macro, args: List[str]) -> str:
    body = macro.body
    for name, value in zip(macro.params or [], args):
        body = re.sub(rf"(?<![\w$]){re.escape(name)}(?!\w)", lambda _m: value, body)  # noqa: B023
    return body
