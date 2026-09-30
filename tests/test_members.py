"""Chapter 3.4 to 3.7: fields, methods, visibility, modifiers, separators."""

from plantuml_converter import MemberKind, Separator, SeparatorStyle, Visibility
from plantuml_converter.members import parse_member


def test_visibility_characters():
    cases = {"-a": Visibility.PRIVATE, "#a": Visibility.PROTECTED, "~a": Visibility.PACKAGE_PRIVATE, "+a": Visibility.PUBLIC}
    for text, visibility in cases.items():
        assert parse_member(text).visibility is visibility
    assert parse_member("+ getName()").name == "getName"
    assert parse_member("plain").visibility is None


def test_field_or_method_is_decided_by_parentheses():
    assert parse_member("size()").kind is MemberKind.METHOD
    assert parse_member("Object[] elementData").kind is MemberKind.FIELD


def test_forced_kind_modifiers():
    text = "{field} A field (despite parentheses)"
    member = parse_member(text)
    assert member.kind is MemberKind.FIELD and member.name == text[len("{field} ") :]
    assert parse_member("{method} Some method").kind is MemberKind.METHOD


def test_static_and_abstract_at_start_or_end():
    assert parse_member("{static} String id").is_static
    assert parse_member("{classifier} String id").is_static
    assert parse_member("String id {static}").is_static
    assert parse_member("{abstract} void methods()").is_abstract
    assert parse_member("void methods() {abstract}").is_abstract
    both = parse_member("+ {static} {abstract} foo()")
    assert both.is_static and both.is_abstract and both.visibility is Visibility.PUBLIC


def test_flexible_type_name_order():
    java = parse_member("String data")
    assert (java.name, java.type) == ("data", "String")
    uml = parse_member("flightNumber : Integer")
    assert (uml.name, uml.type) == ("flightNumber", "Integer")
    generic = parse_member("Map<String, int> values")
    assert (generic.name, generic.type) == ("values", "Map<String, int>")
    scoped = parse_member("std::string name")
    assert (scoped.name, scoped.type) == ("name", "std::string")


def test_default_value():
    member = parse_member("int x = 5")
    assert (member.name, member.type, member.default_value) == ("x", "int", "5")
    assert parse_member("a == b").default_value is None


def test_method_signatures():
    m = parse_member("+ run(a : int, List<String> b, c) : Result")
    assert (m.name, m.type) == ("run", "Result")
    assert [(p.name, p.type) for p in m.parameters] == [("a", "int"), ("b", "List<String>"), ("c", None)]
    m = parse_member("void foo(Map<A, B> m)")
    assert (m.name, m.type, len(m.parameters)) == ("foo", "void", 1)
    assert parse_member("broken(a").name == "broken(a"


def test_separators():
    for text, style in {"--": SeparatorStyle.DASHED, "..": SeparatorStyle.DOTTED, "==": SeparatorStyle.DOUBLE, "__": SeparatorStyle.UNDERLINE}.items():
        sep = parse_member(text)
        assert isinstance(sep, Separator) and sep.style is style and sep.title is None
    titled = parse_member(".. Simple Getter ..")
    assert titled.style is SeparatorStyle.DOTTED and titled.title == "Simple Getter"
    assert parse_member("-- encrypted --").title == "encrypted"


def test_empty_line():
    assert parse_member("   ") is None


def test_body_keeps_members_and_separators_in_order(compile_diagram):
    d = compile_diagram("class User {\n.. Getters ..\n+ getName()\n__ data __\nint age\n-- x --\n}")
    kinds = [type(m).__name__ for m in d.entities["User"].members]
    assert kinds == ["Separator", "Member", "Separator", "Member", "Separator"]
    assert [m.name for m in d.entities["User"].methods] == ["getName"]
    assert [m.name for m in d.entities["User"].fields] == ["age"]


def test_enum_constants_are_fields(compile_diagram):
    d = compile_diagram("enum TimeUnit {\nDAYS\nHOURS\nMINUTES\n}")
    assert [m.name for m in d.entities["TimeUnit"].fields] == ["DAYS", "HOURS", "MINUTES"]
