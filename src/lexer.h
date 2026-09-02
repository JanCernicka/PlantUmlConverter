#ifndef PLANTUMLCONVERTER_LEXER_H
#define PLANTUMLCONVERTER_LEXER_H

#include <string>
#include <string_view>
#include <unordered_map>
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
// whitespace, so blank lines produce no tokens. A word starting with a double
// quote extends to the closing quote and may contain whitespace; the quotes
// themselves are not part of the lexeme.
class Lexer {
public:
    explicit Lexer(std::string source);

    // Scans the whole source.
    std::vector<Token> tokenize() const;

private:
    // Words that map directly onto a token type. Anything not listed here is
    // an IDENTIFIER.
    static const std::unordered_map<std::string_view, TokenType> keywords_;

    // Returns the keyword token type for a word, or IDENTIFIER if it is not a
    // keyword.
    static TokenType classify(std::string_view word);

    // Reads a whitespace delimited word starting at position and advances
    // position past it.
    std::string scan_word(std::size_t& position) const;

    // Reads a double quoted word starting at position (which must point at the
    // opening quote) and advances position past the closing quote. Returns the
    // text between the quotes. An unterminated quote ends at the end of the
    // line and is reported as an error.
    std::string scan_quoted(std::size_t& position, int line) const;

    std::string source_;
};

}  // namespace plantuml

#endif  // PLANTUMLCONVERTER_LEXER_H
