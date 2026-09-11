"""CLI: argumentos e apresentação, sem heurísticas ou XML."""

import argparse
import unicodedata
from pathlib import Path

from prometeu.application.pipeline import ConversionPipeline
from prometeu.document.contracts import ConversionRequest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prometeu", description="PDF textual para EPUB 3 local.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    convert = subcommands.add_parser("convert", help="Converter um PDF textual, sem rede.")
    convert.add_argument("input", type=Path, help="Arquivo PDF de entrada")
    convert.add_argument("-o", "--output", type=Path, help="Destino; padrão: entrada com .epub")
    convert.add_argument("--title", help="Sobrescrever título")
    convert.add_argument("--author", help="Sobrescrever autor")
    convert.add_argument("--language", help="Idioma BCP 47; desconhecido: und")
    convert.add_argument("--identifier", help="Identificador da publicação")
    convert.add_argument("--force", action="store_true", help="Substituir saída; nunca a entrada")
    args = parser.parse_args(argv)
    result = ConversionPipeline().run(
        ConversionRequest(
            input_path=args.input,
            output_path=args.output,
            title=args.title,
            author=args.author,
            language=args.language,
            identifier=args.identifier,
            overwrite=args.force,
        )
    )
    for diagnostic in result.diagnostics:
        message = f"{diagnostic.severity}: {diagnostic.code}: {diagnostic.message}"
        print(
            "".join(
                f"\\u{ord(char):04x}" if unicodedata.category(char) in {"Cc", "Cf"} else char
                for char in message
            )
        )
    for validation in result.validations:
        print(f"Validação {validation.name}: {validation.status.value}")
    if result.success:
        stats = result.statistics
        print(
            f"EPUB publicado: {stats.pages} páginas, {stats.paragraphs} parágrafos, "
            f"{stats.output_bytes} bytes."
        )
    return result.exit_code
