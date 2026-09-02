#include "lexer.h"

#include <cctype>

#include <spdlog/spdlog.h>

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

const std::unordered_map<std::string_view, TokenType> Lexer::keywords_ = {
    {"@startuml", TokenType::START_UML},
    {"@enduml",   TokenType::END_UML},
};

Lexer::Lexer(std::string source) : source_(std::move(source)) {}

TokenType Lexer::classify(std::string_view word) {
    const auto keyword = keywords_.find(word);
    return keyword == keywords_.end() ? TokenType::IDENTIFIER : keyword->second;
}

std::string Lexer::scan_word(std::size_t& position) const {
    const std::size_t begin = position;
    while (position < source_.size() && !is_space(source_[position])) {
        ++position;
    }
    return source_.substr(begin, position - begin);
}

std::string Lexer::scan_quoted(std::size_t& position, int line) const {
    const std::size_t begin = ++position;  // skip the opening quote
    while (position < source_.size() && source_[position] != '"' &&
           source_[position] != '\n') {
        ++position;
    }

    std::string text = source_.substr(begin, position - begin);
    if (position < source_.size() && source_[position] == '"') {
        ++position;  // skip the closing quote
    } else {
        spdlog::error("line {}: unterminated quote, text \"{}\" runs to end of line",
                      line, text);
    }
    return text;
}

std::vector<Token> Lexer::tokenize() const {
    spdlog::info("lexer started on {} symbols", source_.size());
    std::vector<Token> tokens;

    int line_number = 1;
    std::size_t position = 0;
    bool inside_diagram = false;

    while (position < source_.size()) {
        // Skip whitespace, counting newlines so tokens know their line.
        if (is_space(source_[position])) {
            if (source_[position] == '\n') {
                ++line_number;
            }
            ++position;
            continue;
        }

        std::string word;
        TokenType type;
        if (source_[position] == '"') {
            word = scan_quoted(position, line_number);
            type = TokenType::IDENTIFIER;  // quoted text is never a keyword
        } else {
            word = scan_word(position);
            type = classify(to_lower(word));
        }

        if (type == TokenType::START_UML) {
            if (inside_diagram) {
                spdlog::warn("line {}: @startuml inside an open diagram",
                             line_number);
            }
            inside_diagram = true;
        } else if (type == TokenType::END_UML) {
            if (!inside_diagram) {
                spdlog::warn("line {}: @enduml without a matching @startuml",
                             line_number);
            }
            inside_diagram = false;
        } else if (!inside_diagram) {
            spdlog::debug("line {}: discarding \"{}\" outside diagram",
                          line_number, word);
            continue;
        }

        spdlog::debug("line {}: {} \"{}\"", line_number, to_string(type), word);
        tokens.emplace_back(type, std::move(word), line_number);
    }

    if (inside_diagram) {
        spdlog::error("reached end of input without @enduml");
    }

    spdlog::info("lexer finished with {} tokens", tokens.size());
    return tokens;
}

}  // namespace plantuml
