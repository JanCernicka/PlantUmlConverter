#include "lexer.h"

#include <cctype>

namespace plantuml {
namespace {

// Removes leading and trailing whitespace from a line.
std::string trim(const std::string& text) {
    std::size_t begin = 0;
    while (begin < text.size() &&
           std::isspace(static_cast<unsigned char>(text[begin]))) {
        ++begin;
    }

    std::size_t end = text.size();
    while (end > begin &&
           std::isspace(static_cast<unsigned char>(text[end - 1]))) {
        --end;
    }

    return text.substr(begin, end - begin);
}

std::string to_lower(std::string text) {
    for (char& c : text) {
        c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    }
    return text;
}

// The directive is the first whitespace delimited word of a line. @startuml may
// be followed by a diagram name, so the whole line cannot be compared directly.
std::string first_word(const std::string& line) {
    const std::size_t end = line.find_first_of(" \t");
    return end == std::string::npos ? line : line.substr(0, end);
}

}  // namespace

const char* to_string(TokenType type) {
    switch (type) {
        case TokenType::START_UML:
            return "START_UML";
        case TokenType::END_UML:
            return "END_UML";
        case TokenType::IDENTIFIER:
            return "IDENTIFIER";
        case TokenType::END_OF_FILE:
            return "END_OF_FILE";
    }
    return "UNKNOWN";
}

Lexer::Lexer(std::string source) : source_(std::move(source)) {}

std::vector<Token> Lexer::tokenize() const {
    std::vector<Token> tokens;

    std::size_t line_number = 0;
    std::size_t position = 0;

    while (position <= source_.size()) {
        std::size_t line_end = source_.find('\n', position);
        if (line_end == std::string::npos) {
            line_end = source_.size();
        }

        ++line_number;
        std::string line = trim(source_.substr(position, line_end - position));
        position = line_end + 1;

        if (line.empty()) {
            continue;
        }

        const std::string directive = to_lower(first_word(line));
        if (directive == "@startuml") {
            tokens.emplace_back(TokenType::START_UML, line, line_number);
        } else if (directive == "@enduml") {
            tokens.emplace_back(TokenType::END_UML, line, line_number);
        } else {
            tokens.emplace_back(TokenType::IDENTIFIER, line, line_number);
        }
    }

    tokens.emplace_back(TokenType::END_OF_FILE, "", line_number);
    return tokens;
}

}  // namespace plantuml
