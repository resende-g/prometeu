import os
from pathlib import Path

import pytest
from tests.support.pdf import TextLine, write_pdf

from prometeu.document.contracts import (
    ConversionLimits,
    DocumentKind,
    ExtractionError,
    InputError,
    InspectionResult,
    UnsupportedDocumentError,
)
from prometeu.document.model import PDFMetadata
from prometeu.extraction import PdfPlumberExtractor, pdfplumber_adapter


def test_extracts_unicode_geometry_styles_metadata_and_stable_ids(tmp_path: Path) -> None:
    path = write_pdf(
        tmp_path / "unicode.pdf",
        [
            [
                TextLine("Título — 世界", 72, 760, size=20, bold=True),
                TextLine("ação em ordem", 72, 700),
            ]
        ],
        {"Title": "Livro sintético", "Author": "Pessoa fictícia"},
    )
    extractor = PdfPlumberExtractor()

    inspection = extractor.inspect(path, ConversionLimits(timeout_seconds=10))
    document = extractor.extract(path, inspection, ConversionLimits(timeout_seconds=10))

    assert inspection.kind is DocumentKind.TEXTUAL
    assert inspection.text_pages == (1,)
    assert inspection.metadata.title == "Livro sintético"
    assert [line.text for line in document.pages[0].lines] == ["Título — 世界", "ação em ordem"]
    assert document.pages[0].lines[0].id == "p1-l1"
    assert document.pages[0].lines[0].spans[0].id == "p1-l1-s1"
    assert document.pages[0].lines[0].spans[0].style.bold
    assert document.pages[0].lines[0].bbox.top < document.pages[0].lines[1].bbox.top
    assert document.id.startswith("pdf-") and str(path) not in document.id


def test_classifies_empty_and_rejects_extraction(tmp_path: Path) -> None:
    path = write_pdf(tmp_path / "empty.pdf", [[]])
    extractor = PdfPlumberExtractor()

    inspection = extractor.inspect(path, ConversionLimits(timeout_seconds=10))

    assert inspection.kind is DocumentKind.EMPTY
    assert inspection.blank_pages == (1,)
    with pytest.raises(UnsupportedDocumentError, match="não contém texto") as caught:
        extractor.extract(path, inspection, ConversionLimits(timeout_seconds=10))
    assert caught.value.code == "PDF_EMPTY"


@pytest.mark.parametrize(
    ("limits", "code"),
    [
        (ConversionLimits(max_pages=1, timeout_seconds=10), "PDF_TOO_MANY_PAGES"),
        (ConversionLimits(max_characters=5, timeout_seconds=10), "PDF_TOO_MANY_CHARACTERS"),
        (ConversionLimits(max_input_bytes=10, timeout_seconds=10), "INPUT_TOO_LARGE"),
    ],
)
def test_inspection_enforces_limits(limits: ConversionLimits, code: str) -> None:
    path = Path("tests/fixtures/sample.pdf")

    with pytest.raises(InputError) as caught:
        PdfPlumberExtractor().inspect(path, limits)

    assert caught.value.code == code


def test_extraction_rechecks_character_limit() -> None:
    path = Path("tests/fixtures/sample.pdf")
    extractor = PdfPlumberExtractor()
    inspection = extractor.inspect(path, ConversionLimits(timeout_seconds=10))

    with pytest.raises(InputError) as caught:
        extractor.extract(
            path,
            inspection,
            ConversionLimits(max_characters=5, timeout_seconds=10),
        )

    assert caught.value.code == "PDF_TOO_MANY_CHARACTERS"


def test_malformed_error_is_stable_and_does_not_leak_path_or_text(tmp_path: Path) -> None:
    path = tmp_path / "entrada-sensivel.pdf"
    path.write_bytes(b"texto-sintetico")

    with pytest.raises(ExtractionError) as caught:
        PdfPlumberExtractor().inspect(path, ConversionLimits(timeout_seconds=10))

    assert caught.value.code == "PDF_MALFORMED"
    assert str(path) not in str(caught.value)
    assert "texto-sintetico" not in str(caught.value)


def test_fifo_is_rejected_without_blocking(tmp_path: Path) -> None:
    path = tmp_path / "input.pdf"
    os.mkfifo(path)

    with pytest.raises(InputError) as caught:
        PdfPlumberExtractor().inspect(path, ConversionLimits(timeout_seconds=1))

    assert caught.value.code == "INPUT_NOT_FILE"


def test_invalid_worker_geometry_becomes_stable_extraction_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "input.pdf"
    path.write_bytes(b"stub")
    inspection = InspectionResult(
        DocumentKind.TEXTUAL,
        page_count=1,
        text_pages=(1,),
        visual_only_pages=(),
        blank_pages=(),
        metadata=PDFMetadata(),
    )
    monkeypatch.setattr(
        pdfplumber_adapter,
        "_run",
        lambda *_args: {
            "id": "pdf-stub",
            "pages": [
                {
                    "number": 1,
                    "width": 0,
                    "height": 100,
                    "lines": [],
                    "image_count": 0,
                    "has_visual_content": False,
                }
            ],
            "metadata": {"title": None, "author": None, "language": None},
        },
    )

    with pytest.raises(ExtractionError) as caught:
        PdfPlumberExtractor().extract(path, inspection, ConversionLimits())

    assert caught.value.code == "PDF_EXTRACTION_PROTOCOL"


def test_invalid_pdf_page_geometry_is_an_extraction_error(tmp_path: Path) -> None:
    source = Path("tests/fixtures/sample.pdf").read_bytes()
    path = tmp_path / "invalid-geometry.pdf"
    path.write_bytes(source.replace(b"/MediaBox [0 0 595 842]", b"/MediaBox [0 0 000 842]"))

    with pytest.raises(ExtractionError) as caught:
        PdfPlumberExtractor().inspect(path, ConversionLimits(timeout_seconds=10))

    assert caught.value.code == "PDF_INVALID_GEOMETRY"


def test_real_wall_timeout_supervises_inspection_and_extraction() -> None:
    path = Path("tests/fixtures/sample.pdf")
    extractor = PdfPlumberExtractor()
    inspection = extractor.inspect(path, ConversionLimits(timeout_seconds=10))

    with pytest.raises(ExtractionError) as inspect_error:
        extractor.inspect(path, ConversionLimits(timeout_seconds=0.001))
    with pytest.raises(ExtractionError) as extract_error:
        extractor.extract(path, inspection, ConversionLimits(timeout_seconds=0.001))

    assert inspect_error.value.code == "PDF_INSPECTION_TIMEOUT"
    assert extract_error.value.code == "PDF_EXTRACTION_TIMEOUT"


def test_memory_limit_is_supervised() -> None:
    with pytest.raises(ExtractionError) as caught:
        PdfPlumberExtractor().inspect(
            Path("tests/fixtures/sample.pdf"),
            ConversionLimits(memory_bytes=1, timeout_seconds=10),
        )

    assert caught.value.code == "PDF_INSPECTION_MEMORY_LIMIT"
