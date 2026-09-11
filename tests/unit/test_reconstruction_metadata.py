from dataclasses import replace
from pathlib import Path

import pytest

from prometeu.application.metadata import resolve_metadata
from prometeu.cleaning.normalize import normalize
from prometeu.document.contracts import ConversionRequest, ExportError, InputError
from prometeu.document.model import (
    BoundingBox,
    Chapter,
    Heading,
    Inline,
    Metadata,
    Paragraph,
    PDFMetadata,
    PhysicalDocument,
    PhysicalLine,
    PhysicalPage,
    PhysicalSpan,
    SemanticDocument,
    TextStyle,
)
from prometeu.structure.reconstruct import reconstruct


def line(page, index, text, top, size=12, bold=False):
    box = BoundingBox(72, top, 500, top + size)
    name = f"p{page}-l{index}"
    return PhysicalLine(
        name,
        page,
        box,
        (PhysicalSpan(f"{name}-s1", text, box, TextStyle(size=size, bold=bold)),),
    )


def physical(*pages):
    return PhysicalDocument(
        "digest", tuple(PhysicalPage(i, 595, 842, lines) for i, lines in enumerate(pages, 1))
    )


def test_reflow_preserves_both_page_origins_and_separates_new_paragraph():
    document = physical(
        (line(1, 1, "Uma ação que começa", 770), line(1, 2, "e segue", 785)),
        (line(2, 1, "na página seguinte.", 60), line(2, 2, "Novo parágrafo.", 100)),
    )
    semantic = reconstruct(document, Metadata("Título", "urn:test")).document
    cleaned = normalize(semantic, document).document
    blocks = cleaned.chapters[0].blocks
    assert [b.text for b in blocks] == [
        "Uma ação que começa e segue na página seguinte.",
        "Novo parágrafo.",
    ]
    assert [(o.page, o.line_id) for o in blocks[0].source.lines] == [
        (1, "p1-l1"),
        (1, "p1-l2"),
        (2, "p2-l1"),
    ]
    assert all(run.source.lines for run in blocks[0].runs)
    assert document.pages[0].lines[1].text == "e segue"


@pytest.mark.parametrize(
    "end,start,top,size",
    [
        ("Fim.", "novo", 770, 12),
        ("segue", "Novo", 770, 12),
        ("segue", "novo", 200, 12),
        ("segue", "novo", 770, 20),
    ],
)
def test_uncertain_page_continuity_is_not_merged(end, start, top, size):
    document = physical((line(1, 1, end, top),), (line(2, 1, start, 60, size),))
    result = reconstruct(document, Metadata("Título", "urn:test"))
    assert len(result.document.chapters[0].blocks) == 2


def test_large_bold_single_lines_split_chapters_without_losing_provenance():
    document = physical(
        (
            line(1, 1, "Capítulo 1", 50, 20, True),
            line(1, 2, "Primeiro parágrafo.", 100),
            line(1, 3, "Destaque não estrutural.", 140, 20),
        ),
        (line(2, 1, "Capítulo 2", 50, 20, True), line(2, 2, "Segundo parágrafo.", 100)),
    )

    chapters = reconstruct(document, Metadata("Título", "urn:test")).document.chapters

    assert [chapter.heading.text for chapter in chapters if chapter.heading] == [
        "Capítulo 1",
        "Capítulo 2",
    ]
    assert [chapter.id for chapter in chapters] == ["chapter-p1-l1", "chapter-p2-l1"]
    assert [[block.text for block in chapter.blocks] for chapter in chapters] == [
        ["Primeiro parágrafo.", "Destaque não estrutural."],
        ["Segundo parágrafo."],
    ]
    assert chapters[1].heading is not None
    assert chapters[1].heading.source == document.pages[1].lines[0].source


def test_whitespace_only_normalization_preserves_unicode_hyphens_and_heading():
    original = physical((line(1, 1, "texto", 70),))
    source = original.pages[0].lines[0].source
    runs = (
        Inline("  café\u00a0e\u0301 — guarda-\n", source=source),
        Inline("chuva\u00ad 世界\t ", bold=True, source=source),
    )
    semantic = SemanticDocument(
        "digest",
        Metadata("Título", "urn:test"),
        (Chapter("c", Heading("h", 1, (Inline(" Título\n "),)), (Paragraph("p", runs, source),)),),
    )
    result = normalize(semantic, original)
    chapter = result.document.chapters[0]
    assert chapter.blocks[0].text == "café\u00a0e\u0301 — guarda- chuva\u00ad 世界"
    assert chapter.heading.text == "Título"
    assert chapter.blocks[0].runs[-1].bold
    assert chapter.blocks[0].source == source
    assert result.dehyphenations == result.removed_lines == 0
    assert semantic.chapters[0].blocks[0].text.endswith("\t ")


@pytest.mark.parametrize("bad", ["\x00", "\x08", "\ud800", "\ufffe"])
def test_xml_characters_are_export_errors_not_silent_content_loss(bad):
    original = physical((line(1, 1, "texto", 70),))
    semantic = SemanticDocument(
        "digest",
        Metadata("Título", "urn:test"),
        (Chapter("c", None, (Paragraph("p", (Inline("A" + bad + "B"),)),)),),
    )
    with pytest.raises(ExportError) as caught:
        normalize(semantic, original)
    assert caught.value.code == "XML_CHARACTER" and caught.value.exit_code == 5


def test_metadata_precedence_inference_and_generic_fallback():
    document = physical((line(1, 1, "Livro sintético", 50, 22), line(1, 2, "texto", 100)))
    request = ConversionRequest(Path("nome-pessoal-nao-vira-titulo.pdf"))
    inferred, diagnostics = resolve_metadata(request, PDFMetadata(), "abc", document)
    assert inferred.title == "Livro sintético"
    assert inferred.identifier == "urn:sha256:abc"
    assert inferred.author is None and inferred.language == "und"
    assert "TITLE_INFERRED" in {d.code for d in diagnostics}
    pdf, _ = resolve_metadata(request, PDFMetadata(title="Título PDF"), "abc", document)
    assert pdf.title == "Título PDF"
    override, _ = resolve_metadata(
        replace(request, title="Escolhido"), PDFMetadata(title="PDF"), "abc", document
    )
    assert override.title == "Escolhido"
    generic, _ = resolve_metadata(request, PDFMetadata(title="\x00"), "abc")
    assert generic.title == "Documento sem título"


@pytest.mark.parametrize(
    "kwargs", [{"title": "\x1b[31m"}, {"title": " "}, {"language": "x"}, {"language": "pt_BR"}]
)
def test_invalid_overrides_fail_as_input_error(kwargs):
    with pytest.raises(InputError):
        resolve_metadata(ConversionRequest(Path("sample.pdf"), **kwargs), PDFMetadata(), "abc")
