#include "lexer.h"

#include <cctype>

namespace plantuml {
namespace {

std::string to_lower(std::string text) {
    for (char& c : text) {
        c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    }
    return text;
}

bool is_space(char c) {
    return std::isspace(static_cast<unsigned char>(c)) != 0;
}

}  // namespace

const char* to_string(TokenType type) {
    switch (type) {
#define X(name) case TokenType::name: return #name;
        TOKEN_TYPES
#undef X
    }

    return "UNKNOWN";
}

Lexer::Lexer(std::string source) : source_(std::move(source)) {}

std::vector<Token> Lexer::tokenize() const {
    std::vector<Token> tokens;

    int line_number = 1;
    std::size_t position = 0;

    while (position < source_.size()) {
        // Skip whitespace, counting newlines so tokens know their line.
        if (is_space(source_[position])) {
            if (source_[position] == '\n') {
                ++line_number;
            }
            ++position;
            continue;
        }

        std::size_t word_end = position;
        while (word_end < source_.size() && !is_space(source_[word_end])) {
            ++word_end;
        }

        std::string word = source_.substr(position, word_end - position);
        position = word_end;

        const std::string directive = to_lower(word);
        if (directive == "@startuml") {
            tokens.emplace_back(TokenType::START_UML, word, line_number);
        } else if (directive == "@enduml") {
            tokens.emplace_back(TokenType::END_UML, word, line_number);
        } else {
            tokens.emplace_back(TokenType::IDENTIFIER, word, line_number);
        }
    }

    tokens.emplace_back(TokenType::END_OF_FILE, "", line_number);
    return tokens;
}

}  // namespace plantuml
