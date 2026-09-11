from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import pytest

from prometeu.document.contracts import ConversionLimits, ExportOptions, ValidationStatus
from prometeu.document.model import Chapter, Inline, Metadata, Paragraph, SemanticDocument
from prometeu.epub import EPUBBuilder
from prometeu.validation import InternalEPUBValidator


def _valid_epub(path: Path, chapter_count: int = 1) -> None:
    document = SemanticDocument(
        "documento-1",
        Metadata("Livro sintético", "urn:prometeu:teste", "pt-BR"),
        tuple(
            Chapter(
                f"capitulo-{index}",
                None,
                (Paragraph(f"p-{index}", (Inline(f"Conteúdo {index}."),)),),
            )
            for index in range(1, chapter_count + 1)
        ),
    )
    EPUBBuilder().export(document, path, ExportOptions(datetime(2026, 1, 2, tzinfo=UTC)))


def _rewrite(
    path: Path, replacements: dict[str, bytes], extras: dict[str, bytes] | None = None
) -> None:
    with ZipFile(path) as source:
        entries = [
            (info.filename, info.compress_type, replacements.get(info.filename, source.read(info)))
            for info in source.infolist()
        ]
    with ZipFile(path, "w") as target:
        for name, compression, data in entries:
            info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = compression
            target.writestr(info, data)
        for name, data in (extras or {}).items():
            target.writestr(name, data, compress_type=ZIP_DEFLATED)


def _code(path: Path, limits: ConversionLimits | None = None) -> str | None:
    result = InternalEPUBValidator().validate(path, limits or ConversionLimits())
    if result.status is ValidationStatus.PASSED:
        return None
    return result.diagnostics[0].code


def test_builder_output_passes_internal_validation(tmp_path: Path) -> None:
    path = tmp_path / "livro.epub"
    _valid_epub(path)

    result = InternalEPUBValidator().validate(path, ConversionLimits())

    assert result.name == "internal"
    assert result.status is ValidationStatus.PASSED
    assert result.diagnostics == ()


def test_mimetype_must_be_first_and_stored(tmp_path: Path) -> None:
    path = tmp_path / "livro.epub"
    _valid_epub(path)
    with ZipFile(path) as source:
        entries = [(info.filename, source.read(info)) for info in source.infolist()]
    with ZipFile(path, "w") as target:
        for name, data in reversed(entries):
            target.writestr(name, data, compress_type=ZIP_DEFLATED)

    assert _code(path) == "EPUB_MIMETYPE_ORDER"


def test_mimetype_local_header_cannot_have_extra_fields(tmp_path: Path) -> None:
    path = tmp_path / "livro.epub"
    info = ZipInfo("mimetype", (1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_STORED
    info.extra = b"\x01\x00\x00\x00"
    with ZipFile(path, "w") as archive:
        archive.writestr(info, b"application/epub+zip")

    assert _code(path) == "EPUB_MIMETYPE_HEADER"


def test_utf16_dtd_and_entity_are_rejected_before_xml_parsing(tmp_path: Path) -> None:
    path = tmp_path / "livro.epub"
    _valid_epub(path)
    hostile = """<?xml version="1.0" encoding="utf-16"?>
<!DOCTYPE container [<!ENTITY x "valor">]>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
<rootfiles><rootfile full-path="EPUB/package.opf"
media-type="application/oebps-package+xml"/></rootfiles></container>""".encode("utf-16")
    _rewrite(path, {"META-INF/container.xml": hostile})

    assert _code(path) == "EPUB_XML_DECLARATION"


@pytest.mark.parametrize(
    ("replacement", "expected"),
    [
        (b'<script xmlns="http://www.w3.org/1999/xhtml"/>', "EPUB_ACTIVE_CONTENT"),
        (b'<p xmlns="http://www.w3.org/1999/xhtml" onclick="x()"/>', "EPUB_ACTIVE_CONTENT"),
        (
            b'<a xmlns="http://www.w3.org/1999/xhtml" href="https://example.invalid/x">x</a>',
            "EPUB_LINK_UNSAFE",
        ),
    ],
)
def test_active_or_remote_content_is_rejected(
    tmp_path: Path, replacement: bytes, expected: str
) -> None:
    path = tmp_path / "livro.epub"
    _valid_epub(path)
    with ZipFile(path) as source:
        chapter = source.read("EPUB/chapter-0001.xhtml")
    chapter = chapter.replace(b"</body>", replacement + b"</body>")
    _rewrite(path, {"EPUB/chapter-0001.xhtml": chapter})

    assert _code(path) == expected


def test_traversal_entry_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "livro.epub"
    _valid_epub(path)
    _rewrite(path, {}, {"../fora.xhtml": b"<html/>"})

    assert _code(path) == "EPUB_ENTRY_PATH"


def test_missing_navigation_anchor_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "livro.epub"
    _valid_epub(path)
    with ZipFile(path) as source:
        nav = source.read("EPUB/nav.xhtml")
    nav = nav.replace(b'chapter-0001.xhtml"', b'chapter-0001.xhtml#ausente"', 1)
    _rewrite(path, {"EPUB/nav.xhtml": nav})

    assert _code(path) == "EPUB_ANCHOR_INVALID"


def test_manifest_and_spine_must_be_coherent(tmp_path: Path) -> None:
    path = tmp_path / "livro.epub"
    _valid_epub(path)
    with ZipFile(path) as source:
        package = source.read("EPUB/package.opf")
    package = package.replace(b'idref="chapter-1"', b'idref="inexistente"')
    _rewrite(path, {"EPUB/package.opf": package})

    assert _code(path) == "EPUB_SPINE_INVALID"


def test_undeclared_archive_member_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "livro.epub"
    _valid_epub(path)
    _rewrite(path, {}, {"EPUB/oculto.txt": "conteúdo".encode()})

    assert _code(path) == "EPUB_UNDECLARED_ENTRY"


def test_archive_and_uncompressed_limits_are_enforced(tmp_path: Path) -> None:
    path = tmp_path / "livro.epub"
    _valid_epub(path)
    limit = path.stat().st_size - 1

    assert _code(path, ConversionLimits(max_output_bytes=limit)) == "EPUB_SIZE_LIMIT"

    with ZipFile(path) as source:
        chapter = source.read("EPUB/chapter-0001.xhtml")
    chapter = chapter.replace("Conteúdo 1.".encode(), b"A" * 50_000)
    _rewrite(path, {"EPUB/chapter-0001.xhtml": chapter})
    assert path.stat().st_size < 10_000
    assert _code(path, ConversionLimits(max_output_bytes=10_000)) == "EPUB_UNCOMPRESSED_LIMIT"


def test_entry_count_is_bounded_before_content_is_read(tmp_path: Path) -> None:
    path = tmp_path / "muitas-entradas.epub"
    with ZipFile(path, "w") as archive:
        archive.writestr("mimetype", b"application/epub+zip", compress_type=ZIP_STORED)
        for index in range(10_000):
            archive.writestr(f"EPUB/{index}.txt", b"")

    assert _code(path) == "EPUB_ENTRY_LIMIT"


def test_navigation_must_cover_every_spine_item_in_order(tmp_path: Path) -> None:
    path = tmp_path / "livro.epub"
    _valid_epub(path, chapter_count=2)
    with ZipFile(path) as source:
        nav = ET.fromstring(source.read("EPUB/nav.xhtml"))
    namespace = "http://www.w3.org/1999/xhtml"
    toc = next(nav.iter(f"{{{namespace}}}nav"))
    listing = toc.find(f"{{{namespace}}}ol")
    assert listing is not None
    listing.remove(listing[-1])
    _rewrite(
        path,
        {"EPUB/nav.xhtml": ET.tostring(nav, encoding="utf-8", xml_declaration=True)},
    )

    assert _code(path) == "EPUB_NAV_INVALID"


def test_modified_metadata_must_be_unique_and_real_utc_time(tmp_path: Path) -> None:
    path = tmp_path / "livro.epub"
    _valid_epub(path)
    with ZipFile(path) as source:
        package = source.read("EPUB/package.opf")
    package = package.replace(b"2026-01-02T00:00:00Z", b"2026-02-31T00:00:00Z")
    _rewrite(path, {"EPUB/package.opf": package})

    assert _code(path) == "EPUB_METADATA_INVALID"


def test_malformed_xml_returns_failed_without_exposing_path(tmp_path: Path) -> None:
    path = tmp_path / "nome-privado.epub"
    _valid_epub(path)
    _rewrite(path, {"EPUB/nav.xhtml": b"<html>"})

    result = InternalEPUBValidator().validate(path, ConversionLimits())

    assert result.status is ValidationStatus.FAILED
    assert result.diagnostics[0].code == "EPUB_XML_INVALID"
    assert str(path) not in result.diagnostics[0].message
