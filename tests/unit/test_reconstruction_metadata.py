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


def test_typographic_tiers_reconstruct_h1_h2_h3_in_order_with_provenance():
    document = physical(
        (
            line(1, 1, "Capítulo", 50, 20, True),
            line(1, 2, "Abertura.", 90),
            line(1, 3, "Seção", 130, 16, True),
            line(1, 4, "Desenvolvimento.", 170),
            line(1, 5, "Subseção", 210, 14, True),
            line(1, 6, "Detalhe.", 250),
            line(1, 7, "Negrito comum.", 290, 12, True),
            line(1, 8, "Título em", 330, 22, True),
            line(1, 9, "duas linhas", 355, 22, True),
        ),
    )

    chapter = reconstruct(document, Metadata("Título", "urn:test")).document.chapters[0]
    headings = ([chapter.heading] if chapter.heading else []) + [
        block for block in chapter.blocks if isinstance(block, Heading)
    ]

    assert [(heading.level, heading.text) for heading in headings] == [
        (1, "Capítulo"),
        (2, "Seção"),
        (3, "Subseção"),
    ]
    assert [heading.id for heading in headings] == [
        "heading-p1-l1",
        "heading-p1-l3",
        "heading-p1-l5",
    ]
    assert [heading.source for heading in headings] == [
        document.pages[0].lines[index].source for index in (0, 2, 4)
    ]
    common = next(block for block in chapter.blocks if block.text == "Negrito comum.")
    assert isinstance(common, Paragraph)
    assert common.runs[0].bold
    assert any(
        isinstance(block, Paragraph) and block.text == "Título em\nduas linhas"
        for block in chapter.blocks
    )


def test_repeated_marginal_text_and_page_numbers_are_not_headings():
    document = physical(
        (
            line(1, 1, "Cabeçalho", 20, 20, True),
            line(1, 2, "Capítulo 1", 100, 20, True),
            line(1, 3, "Texto.", 140),
            line(1, 4, "1", 800, 16, True),
        ),
        (
            line(2, 1, "Cabeçalho", 20, 20, True),
            line(2, 2, "Capítulo 2", 100, 20, True),
            line(2, 3, "Texto.", 140),
            line(2, 4, "2", 800, 16, True),
        ),
    )

    chapters = reconstruct(document, Metadata("Título", "urn:test")).document.chapters

    assert [chapter.heading.text for chapter in chapters if chapter.heading] == [
        "Capítulo 1",
        "Capítulo 2",
    ]
    assert not any(
        isinstance(block, Heading) and block.text in {"Cabeçalho", "1", "2"}
        for chapter in chapters
        for block in chapter.blocks
    )


def test_whitespace_only_normalization_preserves_unicode_hyphens_and_heading():
    original = physical((line(1, 1, "texto", 70),))
    source = original.pages[0].lines[0].source
    runs = (
        Inline("  café\u00a0é — guarda-\n", source=source),
        Inline("chuva\u00ad 世界\t ", bold=True, source=source),
    )
    semantic = SemanticDocument(
        "digest",
        Metadata("Título", "urn:test"),
        (
            Chapter(
                "c", Heading("h", 1, (Inline(" Ti\u0301tulo\n "),)), (Paragraph("p", runs, source),)
            ),
        ),
    )
    result = normalize(semantic, original)
    chapter = result.document.chapters[0]
    assert chapter.blocks[0].text == "café\u00a0é — guarda- chuva\u00ad 世界"
    assert chapter.heading.text == "Título"
    assert chapter.blocks[0].runs[-1].bold
    assert chapter.blocks[0].source == source
    assert result.dehyphenations == result.removed_lines == 0
    assert semantic.chapters[0].blocks[0].text.endswith("\t ")


def test_nfc_normalizes_only_semantic_run_text():
    original = physical(
        (
            line(1, 1, "Cafe\u0301 \u2010 \u00ad", 70, bold=True),
            line(1, 2, "Café", 100),
        )
    )
    semantic = reconstruct(original, Metadata("Título", "urn:test")).document

    result = normalize(semantic, original)
    blocks = result.document.chapters[0].blocks

    assert [block.text for block in blocks] == ["Café \u2010 \u00ad", "Café"]
    assert blocks[0].id == "para-p1-l1"
    assert blocks[0].source == original.pages[0].lines[0].source
    assert blocks[0].runs[0].bold
    assert original.pages[0].lines[0].text == semantic.chapters[0].blocks[0].text
    assert result.removed_lines == result.dehyphenations == 0


def test_dehyphenation_requires_a_corroborated_physical_line_break():
    original = physical(
        (
            line(1, 1, "Normalização internamente.", 100),
            line(1, 2, "Outra normali-", 140, bold=True),
            line(1, 3, "zação segue.", 155, bold=True),
            line(1, 4, "Um guarda-", 190),
            line(1, 5, "chuva protege.", 205),
            line(1, 6, "Hífen\u00ad", 240),
            line(1, 7, "macio.", 255),
            line(1, 8, "interna-\nmente intacto.", 290),
            line(1, 9, "Unicode\u2010", 330),
            line(1, 10, "preservado.", 345),
        ),
    )
    semantic = reconstruct(original, Metadata("Título", "urn:test")).document

    result = normalize(semantic, original)
    blocks = result.document.chapters[0].blocks

    assert [block.text for block in blocks] == [
        "Normalização internamente.",
        "Outra normalização segue.",
        "Um guarda- chuva protege.",
        "Hífen\u00ad macio.",
        "interna- mente intacto.",
        "Unicode\u2010 preservado.",
    ]
    positive = blocks[1]
    assert positive.id == "para-p1-l2"
    assert positive.source.lines == (
        original.pages[0].lines[1].source.lines + original.pages[0].lines[2].source.lines
    )
    assert [run.source for run in positive.runs] == [
        original.pages[0].lines[1].source,
        original.pages[0].lines[2].source,
    ]
    assert all(run.bold for run in positive.runs)
    assert result.dehyphenations == 1


def test_normalization_removes_only_simple_pagination_at_page_margins():
    original = physical(
        (
            line(1, 1, "1984", 20, 22, True),
            line(1, 2, "Texto.", 100),
            line(1, 3, "17", 400),
            line(1, 4, "1", 800),
        ),
        (line(2, 1, "2", 20), line(2, 2, "Continuação.", 100)),
    )
    semantic = reconstruct(original, Metadata("Título", "urn:test")).document

    result = normalize(semantic, original)
    chapter = result.document.chapters[0]

    assert chapter.heading is not None and chapter.heading.text == "1984"
    assert [(block.id, block.text) for block in chapter.blocks] == [
        ("para-p1-l2", "Texto."),
        ("para-p1-l3", "17"),
        ("para-p2-l2", "Continuação."),
    ]
    assert [block.source for block in chapter.blocks] == [
        original.pages[0].lines[1].source,
        original.pages[0].lines[2].source,
        original.pages[1].lines[1].source,
    ]
    assert result.removed_lines == 2


def test_sequential_numeric_chapter_titles_are_not_pagination():
    original = physical(
        (line(1, 1, "1", 20, 22, True), line(1, 2, "Corpo um.", 100)),
        (line(2, 1, "2", 20, 22, True), line(2, 2, "Corpo dois.", 100)),
    )

    result = normalize(reconstruct(original, Metadata("Título", "urn:test")).document, original)

    assert [chapter.heading.text for chapter in result.document.chapters if chapter.heading] == [
        "1",
        "2",
    ]
    assert result.removed_lines == 0


def test_bold_body_sized_numbers_at_the_top_are_pagination():
    original = physical(
        (line(1, 1, "1", 20, 12, True), line(1, 2, "Corpo um.", 100)),
        (line(2, 1, "2", 20, 12, True), line(2, 2, "Corpo dois.", 100)),
    )

    result = normalize(reconstruct(original, Metadata("Título", "urn:test")).document, original)

    assert [block.text for chapter in result.document.chapters for block in chapter.blocks] == [
        "Corpo um.",
        "Corpo dois.",
    ]
    assert result.removed_lines == 2


def test_normalization_removes_only_sequenced_decorated_pagination():
    original = physical(
        (
            line(1, 1, "Texto um.", 100),
            line(1, 2, "[17] no corpo.", 400),
            line(1, 3, "Capítulo 17", 770),
            line(1, 4, "- 17 -", 800, 20, True),
        ),
        (
            line(2, 1, "Texto dois.", 100),
            line(2, 2, "- 18 —", 770),
            line(2, 3, "— 18 —", 800, 20, True),
        ),
        (
            line(3, 1, "Texto três.", 100),
            line(3, 2, "[99]", 770),
            line(3, 3, "[19]", 800, 20, True),
        ),
        (
            line(4, 1, "Texto quatro.", 100),
            line(4, 2, "11/09/2026", 760),
            line(4, 3, "Página 99", 786),
            line(4, 4, "Página 20", 812, 20, True),
        ),
    )
    semantic = reconstruct(original, Metadata("Título", "urn:test")).document

    result = normalize(semantic, original)
    blocks = result.document.chapters[0].blocks

    assert [(block.id, block.text) for block in blocks] == [
        ("para-p1-l1", "Texto um."),
        ("para-p1-l2", "[17] no corpo."),
        ("para-p1-l3", "Capítulo 17"),
        ("para-p2-l1", "Texto dois."),
        ("para-p2-l2", "- 18 —"),
        ("para-p3-l1", "Texto três."),
        ("para-p3-l2", "[99]"),
        ("para-p4-l1", "Texto quatro."),
        ("para-p4-l2", "11/09/2026"),
        ("para-p4-l3", "Página 99"),
    ]
    assert blocks[1].source == original.pages[0].lines[1].source
    assert blocks[4].source == original.pages[1].lines[1].source
    assert not any(chapter.heading for chapter in result.document.chapters)
    assert result.removed_lines == 4


def test_normalization_removes_only_repeated_text_in_the_same_margin():
    original = physical(
        (
            line(1, 1, "Relatório", 20),
            line(1, 2, "Alternado", 50),
            line(1, 3, "Texto repetido.", 120),
            line(1, 4, "Rodapé", 800),
        ),
        (
            line(2, 1, "  RELATÓRIO  ", 20),
            line(2, 2, "Texto repetido.", 120),
            line(2, 3, "Alternado", 780),
            line(2, 4, "Rodapé", 820),
        ),
    )
    semantic = reconstruct(original, Metadata("Título", "urn:test")).document

    result = normalize(semantic, original)

    assert [block.text for chapter in result.document.chapters for block in chapter.blocks] == [
        "Alternado",
        "Texto repetido.",
        "Texto repetido.",
        "Alternado",
    ]
    assert result.removed_lines == 4


def test_title_matching_a_repeated_footer_remains_a_heading():
    original = physical(
        (
            line(1, 1, "Capítulo um", 20, 22, True),
            line(1, 2, "Corpo um.", 100),
        ),
        (
            line(2, 1, "Corpo dois.", 100),
            line(2, 2, "Capítulo um", 810),
        ),
        (
            line(3, 1, "Corpo três.", 100),
            line(3, 2, "Capítulo um", 810),
        ),
    )

    result = normalize(reconstruct(original, Metadata("Título", "urn:test")).document, original)

    chapter = result.document.chapters[0]
    assert chapter.heading is not None and chapter.heading.text == "Capítulo um"
    assert [block.text for block in chapter.blocks] == ["Corpo um.", "Corpo dois.", "Corpo três."]
    assert result.removed_lines == 2


def test_repeated_header_does_not_merge_with_body_across_pages():
    original = physical(
        (line(1, 1, "texto continua", 770),),
        (line(2, 1, "cabeçalho", 20), line(2, 2, "corpo dois.", 100)),
        (line(3, 1, "cabeçalho", 20), line(3, 2, "corpo três.", 100)),
    )

    result = normalize(reconstruct(original, Metadata("Título", "urn:test")).document, original)

    assert [block.text for chapter in result.document.chapters for block in chapter.blocks] == [
        "texto continua",
        "corpo dois.",
        "corpo três.",
    ]
    assert result.removed_lines == 2


def test_removed_header_does_not_leave_an_empty_chapter_before_h1():
    original = physical(
        (
            line(1, 1, "cabeçalho", 20),
            line(1, 2, "Capítulo um", 100, 22, True),
            line(1, 3, "corpo um.", 150),
        ),
        (
            line(2, 1, "cabeçalho", 20),
            line(2, 2, "Capítulo dois", 100, 22, True),
            line(2, 3, "corpo dois.", 150),
        ),
    )

    result = normalize(reconstruct(original, Metadata("Título", "urn:test")).document, original)

    assert [chapter.heading.text for chapter in result.document.chapters if chapter.heading] == [
        "Capítulo um",
        "Capítulo dois",
    ]
    assert len(result.document.chapters) == 2
    assert result.removed_lines == 2


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
