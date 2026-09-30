# PlantUmlConverter

A compiler written in Python that reads **PlantUML class diagrams** and produces an
**object model** (plain Python objects). The accepted syntax follows chapter 3
("Class Diagram") and the common commands of chapter 15 of the
[PlantUML Language Reference Guide 1.2020.22](https://pdf.plantuml.net/1.2020.22/PlantUML_Language_Reference_Guide_en.pdf).
All other diagram types (sequence, activity, state, mind map ...) are recognised and ignored.

There are no runtime dependencies, Python 3.9 or newer is enough.

## Quick start

```sh
python -m plantuml_converter examples/sample.plantuml            # summary of the model
python -m plantuml_converter examples/sample.plantuml --format json
python -m plantuml_converter examples/sample.plantuml --log-level DEBUG
```

The model goes to stdout, log messages go to stderr. Optional: `pip install .` adds the
command `plantuml-converter`.

From Python:

```python
from plantuml_converter import compile_file, compile_text, RelationKind

result = compile_file("examples/sample.plantuml")   # or compile_text("@startuml ...")
diagram = result.diagram                             # first class diagram, None if there is none

for entity in diagram.entities.values():
    print(entity.kind.value, entity.qualified_name, [m.name for m in entity.methods])

for rel in diagram.relationships:
    if rel.kind is RelationKind.EXTENSION:
        print(rel.target.name, "extends", rel.source.name)   # A <|-- B means B extends A
```

CLI exit codes: `0` success, `1` errors in the input or no class diagram found,
`2` the file cannot be read or bad arguments.

## The object model

`compile_*` returns a `CompilationResult` with `diagrams` (list of `ClassDiagram`),
`skipped` (blocks that are not class diagrams) and `diagnostics`.
The classes live in `plantuml_converter/model.py`:

| Class | Content |
|---|---|
| `ClassDiagram` | `entities` and `packages` (dicts by qualified name), `root` (package tree), `relationships`, `notes`, `note_links`, `association_classes`, `rules` (hide/show), `skinparams`, `title`, `header`, `footer`, `caption`, `legend`, `direction`, `scale`, `page`, `diagnostics` |
| `Entity` | `kind` (class, abstract class, interface, enum, annotation, entity, circle, diamond), `name`, `qualified_name`, `display_name`, `namespace`, `package`, `generics`, `stereotypes`, `spot`, `color`, `extends`, `implements`, `members`, `implicit` |
| `Member` / `Separator` | field or method (`visibility`, `type`, `parameters`, `is_static`, `is_abstract`, `default_value`) / `--` `..` `==` `__` line with optional title. `Entity.fields` and `Entity.methods` filter the list |
| `Package` | `package`, `namespace` or `together` group with `children` (entities and packages) |
| `Relationship` | `source`, `target` (as written, left to right), `source_head`, `target_head`, `line_style`, `length`, `direction`, `bold`, `hidden`, `color`, `label`, `label_arrow`, cardinalities, `note`, and the derived `kind` (extension, implementation, composition, aggregation, dependency, association ...) |
| `Note`, `NoteLink`, `AssociationClass`, `VisibilityRule` | notes (on entity, on link, floating), floating note connectors, `(A, B) .. C`, `hide` / `show` commands |

References between objects are real object references (`rel.source is diagram.entities["A"]`).
`to_dict()` / `to_json()` (in `serialize.py`) turn the model into plain data where references
become qualified names. Colors are stored without the leading `#`.

## Supported syntax

- **Elements** (3.1): `class`, `abstract`, `abstract class`, `annotation`, `circle`, `()`,
  `diamond`, `<>`, `entity`, `enum`, `interface`; alias and label (`class "Long name" as a`,
  `class a as "Long name"`), generics `Foo<T>`, stereotypes `<<Foo>>` with spots `<< (S,#FF7700) Name >>`,
  colors, `extends` / `implements`, bodies with `{` on the same or the next line.
- **Members** (3.4 to 3.7): `Name : member` and body lines, visibility `- # ~ +`, `{static}`,
  `{classifier}`, `{abstract}`, `{field}`, `{method}` at the start or end, both `Type name` and
  `name : Type` order, parameters, default values, separators with titles.
- **Relationships** (3.2, 3.3, 3.21 to 3.24, 3.31, 3.32): all heads `<|` `*` `o` `<` `x` `#` `}` `+` `^` `()`
  on either side, `--` and `..` bodies of any length, direction keywords (`-left->`, `-d->`), inline
  styles (`-[bold]->`, `-[#red,dashed,thickness=2]->`, `-[hidden]->`), `#line:red;line.bold;text:red`,
  cardinalities, labels with `<` / `>` direction, lollipop interfaces, association classes
  `(A, B) .. C`, links between packages.
- **Packages** (3.17 to 3.20): `package`, `namespace` (qualified names, `.Name` for the default
  namespace, automatic namespace creation from `a.b.Name`), `set namespaceSeparator ::` / `none`, `together`.
- **Notes** (3.8 to 3.10): `note left|right|top|bottom of X`, on the last class, floating `note "..." as N`
  linked with `..`, `note on link`, single line (`: text`) and multi-line (`end note`).
- **Commands**: `hide` / `show`, `skinparam` (single line and block), `title`, `header`, `footer`,
  `caption`, `legend` (single and multi-line), `left to right direction`, `scale`, `page`, comments `'` and `/' '/`.

## How the compiler works

1. **Preprocessor** (`preprocessor.py`) removes comments and cuts the text into `@start...` / `@end...` blocks.
   Text outside of blocks is ignored. A file can contain several diagrams.
2. **Detector** (`detector.py`) decides whether a `@startuml` block is a class diagram. Like PlantUML,
   the first line that only one diagram type understands decides: `class Foo`, `namespace x {`, `A <|-- B`
   mean class diagram, `participant`, `component`, `state`, `start`, `[*] -->`, `(use case)` ... mean something
   else and the block is listed in `result.skipped`. A block without any such line (for example only `a -- b`)
   is treated as a class diagram, because that is what the program is meant to receive.
3. **Parser** (`parser.py`, with `relations.py` and `members.py`) builds the model statement by statement.

## Edge cases and decisions

- **Forward references**: entities used in relationships or notes before (or without) a declaration are created
  as implicit classes (`entity.implicit` is true); a later declaration upgrades them. Declaring a name twice merges
  members; redeclaring it with another kind is a warning and the first kind is kept.
- **Keywords as names**: `abstract abstract`, `class class` and `class --> interface` work.
- **Names**: Unicode letters, dots and `::` in names, quoted names with spaces or punctuation (never split into
  namespaces), `A-->B` without spaces. A head letter directly followed by a word (`--other`) is part of the name;
  write `--o B` with a space for an aggregation.
- **Files**: UTF-8 with or without BOM, otherwise ISO-8859-1 with a warning (or pass `encoding`), any of
  `\n`, `\r\n`, `\r`, tabs, empty input.
- **Comments**: `'` only comments out a whole line (so `don't` in a label is safe), `/' '/` may span lines (an `@enduml` inside
  it does not end the diagram), comment markers inside double quotes are kept.
- **Broken input never crashes the compiler.** A statement that cannot be understood is reported as an
  *error* diagnostic and skipped; things that are ignored on purpose (`!include`, `newpage`, unknown `set`) are
  *warnings*. Unclosed bodies, notes, packages, and a missing `@enduml` are errors, but what was read
  so far is kept. Every diagnostic has the line number in the original file.
- **Strict mode**: `compile_text(text, strict=True)` / `--strict` processes everything and then raises
  `CompilationError` (with the full `result` attached) if there was any error. Warnings never fail.

### Known limitations

- Preprocessor directives (`!include`, `!define`, ...) are not executed, only reported.
- Only the element keywords of chapter 3.1 are known (no `struct`, `protocol`, `object` ...).
- Note, title and legend text is stored raw: `\n` escapes, creole and HTML are not interpreted.
- `skinparam` values are stored as text, `hide` / `show` rules are recorded but not applied to the model.
- Whether `Type name` or `name : Type` is meant in a member is guessed from its shape; free text after
  `{field}` is kept whole as the name.
- A quoted name in a relationship is not matched against the label of an aliased class.

## Logging

The package logs through the standard `logging` module under the logger name `plantuml_converter`
(`.preprocessor`, `.detector`, `.parser`, `.compiler`). As a library it adds only a `NullHandler`, so your
application decides what is shown. The CLI writes to stderr, `--log-level` accepts
`DEBUG`, `INFO` (default), `WARNING`, `ERROR`, `CRITICAL`, `OFF`.

| Level | What you see |
|---|---|
| `DEBUG` | every block, created or declared entity, relationship, member addition, opened and closed package |
| `INFO` | file read, blocks skipped and why, number of entities, relationships and problems per diagram |
| `WARNING` | ignored commands, redeclarations, decoding fallback, no class diagram found |
| `ERROR` | statements that could not be parsed, unclosed blocks |

## Development

```sh
pip install pytest
python -m pytest
```

The tests include all 46 examples of chapter 3 of the reference guide
(`tests/data/reference_guide_chapter3.plantuml`, which must compile without any diagnostic) and a
fuzz test that damages them randomly.

```
plantuml_converter/
  model.py          object model
  preprocessor.py   comments, @start/@end blocks
  detector.py       class diagram or not
  parser.py         statements to model
  relations.py      syntax of relationship lines
  members.py        syntax of fields and methods
  compiler.py       compile_text, compile_file, CompilationResult
  diagnostics.py    warnings, errors, exceptions
  serialize.py      to_dict, to_json, summarize
  cli.py            command line interface
examples/           sample inputs
tests/              pytest suite
```
