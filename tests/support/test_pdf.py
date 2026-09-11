from pathlib import Path

import pdfplumber
import pytest

from tests.fixtures.generate import generate
from tests.support.pdf import TextLine, write_pdf


def test_pdf_preserves_pages_text_unicode_and_metadata(tmp_path: Path):
    path = write_pdf(
        tmp_path / "synthetic.pdf",
        (
            (TextLine("Capítulo 1", 72, 770, 20, True), TextLine("ação — 世界", 72, 730)),
            (),
        ),
        {"Title": "Amostra sintética", "Author": "Projeto Prometeu"},
    )

    with pdfplumber.open(path) as pdf:
        assert len(pdf.pages) == 2
        assert pdf.pages[0].extract_text() == "Capítulo 1\nação — 世界"
        assert pdf.pages[1].extract_text() == ""
        assert pdf.metadata["Title"] == "Amostra sintética"
        assert pdf.metadata["Author"] == "Projeto Prometeu"
    assert b"/ToUnicode" in path.read_bytes()


def test_sample_fixture_is_deterministic_and_exposes_paragraph_spacing(tmp_path: Path):
    first = generate(tmp_path / "first.pdf")
    second = generate(tmp_path / "second.pdf")

    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes() == Path("tests/fixtures/sample.pdf").read_bytes()

    with pdfplumber.open(first) as pdf:
        assert len(pdf.pages) == 2
        lines = pdf.pages[0].extract_text_lines()
        assert [line["text"] for line in lines] == [
            "Capítulo 1 — A origem",
            "A primeira ação começa aqui e",
            "continua na linha seguinte.",
            "Este é outro parágrafo, após um intervalo maior.",
        ]
        assert float(lines[2]["top"]) - float(lines[1]["top"]) == pytest.approx(16)
        assert float(lines[3]["top"]) - float(lines[2]["top"]) == pytest.approx(44)
        assert pdf.pages[1].extract_text() == (
            "Capítulo 2 — Continuidade\n"
            "Unicode extraível: café, ação e 世界.\n"
            "Fim da amostra sintética."
        )


def test_pdf_rejects_more_than_one_byte_of_distinct_characters(tmp_path: Path):
    text = "".join(chr(0x100 + index) for index in range(256))
    with pytest.raises(ValueError, match="255 caracteres"):
        write_pdf(tmp_path / "too-many.pdf", ((TextLine(text, 72, 770),),))


def test_pdf_rejects_unsupported_metadata(tmp_path: Path):
    with pytest.raises(ValueError, match="Metadados PDF não suportados: CreationDate, ModDate"):
        write_pdf(
            tmp_path / "unsupported-metadata.pdf",
            ((),),
            {"ModDate": "today", "CreationDate": "today"},
        )
