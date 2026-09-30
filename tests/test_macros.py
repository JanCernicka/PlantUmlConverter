"""The preprocessor of chapter 20 of the reference guide."""

import logging

import pytest

from plantuml_converter import Severity, compile_text
from plantuml_converter.diagnostics import Reporter
from plantuml_converter.macros import Preprocessor
from plantuml_converter.preprocessor import LogicalLine


def expand(source: str):
    reporter = Reporter(logging.getLogger("test"))
    lines = [LogicalLine(n, text.strip()) for n, text in enumerate(source.strip().split("\n"), start=1)]
    return [line.text for line in Preprocessor(reporter).run(lines)], reporter.items


def test_variables_and_string_concatenation():
    out, problems = expand('!$ab = "foo1"\n!$cd = "foo2"\n!$ef = $ab + $cd\nA : $ab\nA : $cd\nA : $ef')
    assert out == ["A : foo1", "A : foo2", "A : foo1foo2"] and not problems


def test_conditions():
    src = '!$a = 10\n!$ijk = "foo"\nbefore\n!if ($ijk == "foo") && ($a+10>=4)\nyes\n!else\nno\n!endif\nafter'
    assert expand(src)[0] == ["before", "yes", "after"]
    src = "!$x = 2\n!if $x == 1\none\n!elseif $x == 2\ntwo\n!else\nmany\n!endif"
    assert expand(src)[0] == ["two"]
    assert expand("!if 0\n!if 1\nhidden\n!endif\n!endif\nvisible")[0] == ["visible"]


def test_ifdef_and_ifndef():
    out, _ = expand("!$v = 1\n!ifdef $v\nA\n!endif\n!ifndef $w\nB\n!endif\n!ifdef $w\nC\n!endif")
    assert out == ["A", "B"]


def test_boolean_builtins():
    assert expand("!if %true()\nA\n!endif\n!if %not(%true())\nB\n!endif\n!if %false() || 1\nC\n!endif")[0] == ["A", "C"]


def test_while_loop():
    out, _ = expand("!$n = 3\n!while $n != 0\nlap $n\n!$n = $n - 1\n!endwhile")
    assert out == ["lap 3", "lap 2", "lap 1"]


def test_endless_while_is_stopped():
    out, problems = expand("!while 1\nx\n!endwhile")
    assert len(out) == 1000 and [p.severity for p in problems] == [Severity.ERROR]


def test_procedures_from_the_guide():
    src = """
!procedure $msg($source, $destination)
$source --> $destination
!endprocedure
!procedure $init_class($name)
class $name {
$addCommonMethod()
}
!endprocedure
!procedure $addCommonMethod()
toString()
hashCode()
!endprocedure
$init_class("foo1")
$init_class("foo2")
$msg("foo1", "foo2")
"""
    out, problems = expand(src)
    assert out == [
        "class foo1 {", "toString()", "hashCode()", "}",
        "class foo2 {", "toString()", "hashCode()", "}",
        "foo1 --> foo2",
    ] and not problems


def test_return_functions():
    src = '!function $double($a)\n!return $a + $a\n!endfunction\nx $double(3)\ny $double("ab")\n!function $d2($a) !return $a + $a\nz $d2(4)'
    assert expand(src)[0] == ["x 6", "y abab", "z 8"]


def test_default_and_keyword_arguments():
    src = '!function $inc($value, $step=1)\n!return $value + $step\n!endfunction\nx $inc(3)\ny $inc(3, 2)\nz $inc($step=5, $value=1)'
    assert expand(src)[0] == ["x 4", "y 5", "z 6"]
    src = '!procedure t($x, $y="DefaultY")\nx=$x y=$y\n!endprocedure\nt(1, 2)\nt(1)'
    assert expand(src)[0] == ["x=1 y=2", "x=1 y=DefaultY"]


def test_unquoted_function():
    src = '!unquoted function id($text1, $text2="FOO") !return $text1 + $text2\na : id(aa)\nb : id(ab,cd)'
    assert expand(src)[0] == ["a : aaFOO", "b : abcd"]


def test_local_and_global_variables():
    src = '!function $dummy()\n!local $ijk = "local"\n!return "A : " + $ijk\n!endfunction\n!global $ijk = "foo"\nA : $ijk\n$dummy()\nA : $ijk'
    assert expand(src)[0] == ["A : foo", "A : local", "A : foo"]


def test_legacy_define():
    out, _ = expand("!define ENTITY(n) class n <<Entity>>\n!define ROOT base\nENTITY(Foo)\nclass ROOT")
    assert out == ["class Foo <<Entity>>", "class base"]


def test_definelong():
    out, _ = expand("!definelong PAIR(a, b)\nclass a\nclass b\n!enddefinelong\nPAIR(X, Y)")
    assert out == ["class X", "class Y"]


def test_argument_concatenation():
    out, _ = expand('!$prefix = "Gen"\nclass $prefix##Class\n!unquoted procedure P($name)\nclass $name##Impl\n!endprocedure\nP(abc)')
    assert out == ["class GenClass", "class abcImpl"]


def test_string_builtins():
    out, _ = expand('%upper("a") %lower("B") %strlen("abc") %substr("abcdef", 3, 2) %strpos("abcdef", "ef") %intval("42") x%newline()y')
    assert out == ['A b 3 de 4 42 x\\ny']


def test_environment_dependent_builtins_are_left_alone():
    assert expand('footer %date("yyyy")')[0] == ['footer %date("yyyy")']


def test_text_without_macros_is_not_touched():
    out, problems = expand("class A\nA --> B : 50% of $5")
    assert out == ["class A", "A --> B : 50% of $5"] and not problems


@pytest.mark.parametrize("directive", ["!include foo.puml", "!includesub a.puml!X", "!theme plain", "!import x.zip", "!unknown"])
def test_unsupported_directives_warn(directive):
    out, problems = expand(f"{directive}\nclass A")
    assert out == ["class A"] and [p.severity for p in problems] == [Severity.WARNING]


def test_assertion_failure_is_an_error():
    _, problems = expand('!assert 1 == 2 : "nope"')
    assert [p.severity for p in problems] == [Severity.ERROR]


def test_broken_macros_are_errors_not_crashes():
    for src in ["!endif", "!if 1\nx", "!function $f(\nx", "!procedure $p()\nx", '!$a = (1 +', "!$a = 1 / 0", "$undefined(1)", "!return 1"]:
        expand(src)


def test_runaway_recursion_is_stopped():
    out, problems = expand("!procedure $p()\n$p()\n!endprocedure\n$p()")
    assert any(p.severity is Severity.ERROR for p in problems)


def test_macros_work_inside_a_class_diagram_and_keep_line_numbers():
    text = "@startuml\n!procedure $dto($n)\nclass $n <<DTO>>\n!endprocedure\n$dto(\"A\")\nbroken line\n@enduml"
    result = compile_text(text)
    assert result.diagram.entities["A"].stereotypes == ["DTO"]
    (problem,) = result.diagram.diagnostics
    assert problem.line == 6


def test_macros_hide_nothing_from_the_diagram_type_detector():
    # the participant only exists after expansion
    text = "@startuml\n!define P participant\nP Alice\n@enduml"
    assert not compile_text(text).diagrams


def test_diagnostics_of_skipped_blocks_are_not_logged(caplog):
    with caplog.at_level(logging.WARNING, logger="plantuml_converter"):
        compile_text("@startuml\n!include x.puml\nparticipant A\n@enduml")
    assert "!include" not in caplog.text


def test_exponential_recursion_is_cut_off_quickly():
    src = "!function $f($a)\n!return $f($a) + $f($a)\n!endfunction\nx $f(1)"
    out, problems = expand(src)
    assert any(p.severity is Severity.ERROR for p in problems)
