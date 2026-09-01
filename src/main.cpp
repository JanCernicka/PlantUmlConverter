#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

#include "lexer.h"

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: plantumlconverter <file.plantuml>\n";
        return 1;
    }

    const std::string path = argv[1];
    std::ifstream input(path);
    if (!input) {
        std::cerr << "error: cannot open '" << path << "'\n";
        return 1;
    }

    std::ostringstream buffer;
    buffer << input.rdbuf();

    const plantuml::Lexer lexer(buffer.str());
    for (const plantuml::Token& token : lexer.tokenize()) {
        std::cout << token.line << ": " << plantuml::to_string(token.type);
        if (!token.lexeme.empty()) {
            std::cout << " \"" << token.lexeme << "\"";
        }
        std::cout << '\n';
    }

    return 0;
}
