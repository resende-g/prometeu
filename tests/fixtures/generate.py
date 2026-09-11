"""Regenera as fixtures PDF originais do projeto (Apache-2.0)."""

from pathlib import Path

from tests.support.pdf import TextLine, write_pdf


def generate(path: Path) -> Path:
    return write_pdf(
        path,
        (
            (
                TextLine("Capítulo 1 — A origem", 72, 770, 20, True),
                TextLine("A primeira ação começa aqui e", 72, 730),
                TextLine("continua na linha seguinte.", 72, 714),
                TextLine("Este é outro parágrafo, após um intervalo maior.", 72, 670),
            ),
            (
                TextLine("Capítulo 2 — Continuidade", 72, 770, 20, True),
                TextLine("Unicode extraível: café, ação e 世界.", 72, 730),
                TextLine("Fim da amostra sintética.", 72, 690),
            ),
        ),
        {"Title": "Amostra sintética", "Author": "Projeto Prometeu"},
    )


def main() -> None:
    generate(Path(__file__).with_name("sample.pdf"))


if __name__ == "__main__":
    main()
