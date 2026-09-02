#ifndef PLANTUMLCONVERTER_LEXER_H
#define PLANTUMLCONVERTER_LEXER_H

#include <string>
#include <vector>

namespace plantuml {

#define TOKEN_TYPES \
    X(START_UML)    \
    X(END_UML)      \
    X(IDENTIFIER)   \
    X(END_OF_FILE)

enum class TokenType {
#define X(name) name,
    TOKEN_TYPES
#undef X
};

// Human readable name of a token type, used for diagnostics.
const char* to_string(TokenType type);

struct Token {
    TokenType type;
    std::string lexeme;  // the source text the token was produced from
    int line;            // 1-based line number in the source

    Token(TokenType type, std::string lexeme, int line)
        : type(type), lexeme(std::move(lexeme)), line(line) {}
};

// Line based lexer for the PlantUML class diagram subset.
//
// At this stage it only recognises the diagram delimiters: a line starting with
// @startuml becomes START_UML, a line starting with @enduml becomes END_UML and
// every other non-empty line becomes a single IDENTIFIER token holding the
// trimmed line. Blank lines carry no content and are skipped.
class Lexer {
public:
    explicit Lexer(std::string source);

    // Scans the whole source. The returned vector always ends with END_OF_FILE.
    std::vector<Token> tokenize() const;

private:
    std::string source_;
};

}  // namespace plantuml

#endif  // PLANTUMLCONVERTER_LEXER_H
