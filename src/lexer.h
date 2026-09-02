#ifndef PLANTUMLCONVERTER_LEXER_H
#define PLANTUMLCONVERTER_LEXER_H

#include <string>
#include <vector>

namespace plantuml {

#define TOKEN_TYPES \
    X(START_UML)    \
    X(END_UML)      \
    X(IDENTIFIER)

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

// Whitespace separated lexer for the PlantUML class diagram subset.
//
// At this stage it only recognises the diagram delimiters: the word @startuml
// becomes START_UML, the word @enduml becomes END_UML and every other word
// between the two delimiters becomes an IDENTIFIER token. Words outside a
// @startuml ... @enduml block are discarded. Words are separated by any
// whitespace, so blank lines produce no tokens.
class Lexer {
public:
    explicit Lexer(std::string source);

    // Scans the whole source.
    std::vector<Token> tokenize() const;

private:
    std::string source_;
};

}  // namespace plantuml

#endif  // PLANTUMLCONVERTER_LEXER_H
