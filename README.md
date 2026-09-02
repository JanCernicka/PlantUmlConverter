# PlantUmlConverter

A C++17 tool that reads a PlantUML class diagram and turns it into an object
model. The project is at an early stage: today it contains only the lexer,
which splits the input into tokens and logs them.

## Requirements

- CMake 3.16 or newer
- A C++17 compiler (GCC, Clang or MSVC)
- Internet access during the first configure step, because the
  [spdlog](https://github.com/gabime/spdlog) logging library is fetched
  automatically by CMake

## Building

From the repository root:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

The executable is written to `build/plantumlconverter` (on Windows with Visual
Studio generators it lands in `build/Release/plantumlconverter.exe`).

## Running

The program takes exactly one argument, the path to a `.plantuml` file:

```sh
./build/plantumlconverter examples/sample.plantuml
```

Expected output with the default logging level:

```
[2026-09-02 10:35:01.556] [info] opened 'examples/sample.plantuml'
[2026-09-02 10:35:01.556] [info] read 120 symbols from 'examples/sample.plantuml'
[2026-09-02 10:35:01.556] [info] lexer started on 120 symbols
[2026-09-02 10:35:01.556] [info] lexer finished with 21 tokens
```

The exit code is 0 on success and 1 when the argument is missing or the file
cannot be opened or read.

### Step by step tutorial

1. Create a file called `hello.plantuml` with this content:

   ```
   @startuml "My Project"
   class Customer
   @enduml
   ```

2. Run the converter with token logging enabled:

   ```sh
   SPDLOG_LEVEL=debug ./build/plantumlconverter hello.plantuml
   ```

3. Read the output. Every token the lexer produced is listed with its line
   number, type and text:

   ```
   [info] opened 'hello.plantuml'
   [info] read 46 symbols from 'hello.plantuml'
   [info] lexer started on 46 symbols
   [debug] line 1: START_UML "@startuml"
   [debug] line 1: IDENTIFIER "My Project"
   [debug] line 2: IDENTIFIER "class"
   [debug] line 2: IDENTIFIER "Customer"
   [debug] line 3: END_UML "@enduml"
   [info] lexer finished with 5 tokens
   ```

## Logging

Logging goes to standard output through spdlog. The level is controlled by the
`SPDLOG_LEVEL` environment variable. When the variable is unset or empty the
level is `info`. An unrecognised value prints a warning and falls back to
`info`.

| Value      | What you see                                                  |
|------------|---------------------------------------------------------------|
| `trace`    | Same as `debug` (no trace messages exist yet)                 |
| `debug`    | Every token and every word discarded outside a diagram block  |
| `info`     | File opened, symbol count, lexer start and finish (default)   |
| `warn`     | Only warnings and errors                                      |
| `error`    | Only errors                                                   |
| `critical` | Nothing at the moment (no critical messages exist yet)        |
| `off`      | Silent                                                        |

Examples:

```sh
# Linux / macOS
SPDLOG_LEVEL=debug ./build/plantumlconverter examples/sample.plantuml
SPDLOG_LEVEL=error ./build/plantumlconverter examples/sample.plantuml

# Windows PowerShell
$env:SPDLOG_LEVEL = "debug"; .\build\Release\plantumlconverter.exe examples\sample.plantuml

# Windows cmd
set SPDLOG_LEVEL=debug && build\Release\plantumlconverter.exe examples\sample.plantuml
```

Warnings and errors reported by the lexer:

- `@startuml` while a diagram is already open (warning)
- `@enduml` without a preceding `@startuml` (warning)
- a double quote that is never closed on the same line (error)
- end of input reached without `@enduml` (error)

## What the lexer does

- Words are separated by whitespace.
- `@startuml` becomes `START_UML` and `@enduml` becomes `END_UML`; the
  comparison is case-insensitive.
- Any other word inside a `@startuml` ... `@enduml` block becomes an
  `IDENTIFIER`.
- Text wrapped in double quotes is a single `IDENTIFIER` even when it contains
  spaces. The quotes are not part of the token.
- Everything outside a diagram block is discarded.

## Project layout

```
CMakeLists.txt            build configuration, fetches spdlog
src/main.cpp              reads the input file, configures logging, runs the lexer
src/lexer.h, lexer.cpp    token types and the lexer
examples/sample.plantuml  sample input
```
