from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_STORED, ZipFile

import pytest

from prometeu.document.contracts import ExportError, ExportOptions
from prometeu.document.model import Chapter, Heading, Inline, Metadata, Paragraph, SemanticDocument
from prometeu.epub import EPUBBuilder

_XHTML = "http://www.w3.org/1999/xhtml"
_EPUB = "http://www.idpf.org/2007/ops"


def _document(
    *, heading: Heading | None = None, blocks: tuple[Heading | Paragraph, ...] = ()
) -> SemanticDocument:
    return SemanticDocument(
        "documento-1",
        Metadata("Título sintético", "urn:prometeu:teste", "pt-BR", "Autoria fictícia"),
        (Chapter("capitulo-1", heading, blocks),),
    )


def _export(path: Path, document: SemanticDocument) -> None:
    EPUBBuilder().export(document, path, ExportOptions(datetime(2026, 1, 2, tzinfo=UTC)))


def test_export_preserves_block_order_and_inline_styles(tmp_path: Path) -> None:
    heading = Heading("titulo-1", 1, (Inline("Capítulo"),))
    section = Heading("secao-1", 2, (Inline("Seção"),))
    paragraph = Paragraph(
        "paragrafo-1",
        (
            Inline("normal "),
            Inline("forte", bold=True),
            Inline(" e "),
            Inline("ênfase", italic=True),
            Inline(" ambos", bold=True, italic=True),
        ),
    )
    trailing = Paragraph("paragrafo-2", (Inline("Fim."),))
    output = tmp_path / "livro.epub"

    _export(output, _document(heading=heading, blocks=(paragraph, section, trailing)))

    with ZipFile(output) as epub:
        assert epub.infolist()[0].filename == "mimetype"
        assert epub.infolist()[0].compress_type == ZIP_STORED
        chapter = ET.fromstring(epub.read("EPUB/chapter-0001.xhtml"))
        nav = ET.fromstring(epub.read("EPUB/nav.xhtml"))
    body = chapter.find(f"{{{_XHTML}}}body")
    assert body is not None
    assert [element.tag.rsplit("}", 1)[-1] for element in body] == ["h1", "p", "h2", "p"]
    content = body[1]
    assert "".join(content.itertext()) == "normal forte e ênfase ambos"
    assert [element.tag.rsplit("}", 1)[-1] for element in content] == [
        "strong",
        "em",
        "strong",
    ]
    assert content[2][0].tag == f"{{{_XHTML}}}em"
    assert all(
        listing.find(f"{{{_XHTML}}}li") is not None for listing in nav.iter(f"{{{_XHTML}}}ol")
    )


def test_chapter_without_heading_has_valid_navigation_without_visible_title(tmp_path: Path) -> None:
    output = tmp_path / "livro.epub"
    _export(output, _document(blocks=(Paragraph("p-1", (Inline("Conteúdo."),)),)))

    with ZipFile(output) as epub:
        nav = ET.fromstring(epub.read("EPUB/nav.xhtml"))
        chapter = ET.fromstring(epub.read("EPUB/chapter-0001.xhtml"))
    toc = next(
        node for node in nav.iter(f"{{{_XHTML}}}nav") if node.get(f"{{{_EPUB}}}type") == "toc"
    )
    links = list(toc.iter(f"{{{_XHTML}}}a"))
    assert [(link.text, link.get("href")) for link in links] == [
        ("Título sintético", "chapter-0001.xhtml")
    ]
    assert all(
        listing.find(f"{{{_XHTML}}}li") is not None for listing in toc.iter(f"{{{_XHTML}}}ol")
    )
    body = chapter.find(f"{{{_XHTML}}}body")
    assert body is not None
    assert [element.tag.rsplit("}", 1)[-1] for element in body] == ["p"]


def test_empty_document_still_has_a_navigable_content_document(tmp_path: Path) -> None:
    document = SemanticDocument(
        "documento-vazio", Metadata("Título sintético", "urn:prometeu:vazio", "pt-BR"), ()
    )
    output = tmp_path / "livro.epub"

    _export(output, document)

    with ZipFile(output) as epub:
        nav = ET.fromstring(epub.read("EPUB/nav.xhtml"))
        assert "EPUB/chapter-0001.xhtml" in epub.namelist()
    link = next(nav.iter(f"{{{_XHTML}}}a"))
    assert link.text == "Título sintético"
    assert link.get("href") == "chapter-0001.xhtml"


def test_incompatible_xml_text_is_an_export_error(tmp_path: Path) -> None:
    document = _document(blocks=(Paragraph("p-1", (Inline("texto\x00hostil"),)),))
    output = tmp_path / "livro.epub"

    with pytest.raises(ExportError) as caught:
        _export(output, document)

    assert caught.value.exit_code == 5
    assert caught.value.code == "EPUB_XML_CHARACTER"
    assert not output.exists()


def test_builder_does_not_create_the_destination_directory_or_leak_its_path(tmp_path: Path) -> None:
    output = tmp_path / "ausente" / "livro.epub"

    with pytest.raises(ExportError) as caught:
        _export(output, _document())

    assert caught.value.code == "EPUB_EXPORT_FAILED"
    assert str(output) not in str(caught.value)
    assert caught.value.__cause__ is None
    assert not output.parent.exists()


def test_output_limit_is_enforced(tmp_path: Path) -> None:
    output = tmp_path / "livro.epub"
    with pytest.raises(ExportError) as caught:
        EPUBBuilder().export(
            _document(),
            output,
            ExportOptions(datetime(2026, 1, 2, tzinfo=UTC), max_output_bytes=32),
        )
    assert caught.value.code == "EPUB_OUTPUT_LIMIT"
