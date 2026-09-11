from __future__ import annotations

import hashlib
import zipfile
from collections.abc import Iterable
from datetime import UTC
from pathlib import Path
from typing import BinaryIO, cast
from xml.etree import ElementTree as ET

from prometeu.document.contracts import ExportError, ExportOptions
from prometeu.document.model import Chapter, Heading, Inline, Paragraph, SemanticDocument

_CONTAINER = "META-INF/container.xml"
_OPF = "EPUB/package.opf"
_NAV = "EPUB/nav.xhtml"
_CSS = "EPUB/styles.css"
_MIMETYPE = b"application/epub+zip"
_XHTML_NS = "http://www.w3.org/1999/xhtml"
_EPUB_NS = "http://www.idpf.org/2007/ops"
_OPF_NS = "http://www.idpf.org/2007/opf"
_DC_NS = "http://purl.org/dc/elements/1.1/"
_CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
_XML_NS = "http://www.w3.org/XML/1998/namespace"
_CSS_TEXT = "h1, h2, h3 { break-after: avoid; }\n"

ET.register_namespace("", _XHTML_NS)
ET.register_namespace("epub", _EPUB_NS)
ET.register_namespace("dc", _DC_NS)


class _LimitedWriter:
    def __init__(self, raw: BinaryIO, limit: int) -> None:
        self.raw = raw
        self.limit = limit

    def write(self, data: bytes) -> int:
        if self.raw.tell() + len(data) > self.limit:
            raise ExportError("EPUB_OUTPUT_LIMIT", "EPUB excede o limite de saída.")
        return self.raw.write(data)

    def __getattr__(self, name: str) -> object:
        return getattr(self.raw, name)


class EPUBBuilder:
    def export(self, document: SemanticDocument, path: Path, options: ExportOptions) -> None:
        _validate_document(document)
        try:
            with path.open("wb") as raw:
                writer = cast(BinaryIO, _LimitedWriter(raw, options.max_output_bytes))
                with zipfile.ZipFile(writer, "w", allowZip64=False) as epub:
                    epub.writestr(_zip_info("mimetype", zipfile.ZIP_STORED), _MIMETYPE)
                    _write_xml(epub, _CONTAINER, _container())
                    chapters = tuple(
                        _chapter(document, chapter, index)
                        for index, chapter in enumerate(document.chapters, 1)
                    )
                    if not chapters:
                        chapters = ((_content_path(1), _empty_content(document)),)
                    _write_xml(epub, _NAV, _navigation(document, len(chapters)))
                    epub.writestr(_zip_info(_CSS), _CSS_TEXT.encode())
                    for name, root in chapters:
                        _write_xml(epub, name, root)
                    _write_xml(epub, _OPF, _package(document, chapters, options))
        except ExportError:
            raise
        except (OSError, UnicodeError, ValueError, zipfile.BadZipFile):
            raise ExportError("EPUB_EXPORT_FAILED", "Falha ao gerar o arquivo EPUB.") from None


def _validate_document(document: SemanticDocument) -> None:
    required = {
        "título": document.metadata.title,
        "identificador": document.metadata.identifier,
        "idioma": document.metadata.language,
    }
    for label, value in required.items():
        if not value.strip():
            raise ExportError("EPUB_METADATA_INVALID", f"Metadado obrigatório vazio: {label}.")
    values: list[str] = [*required.values()]
    if document.metadata.author is not None:
        values.append(document.metadata.author)
    for chapter in document.chapters:
        headings = ([chapter.heading] if chapter.heading else []) + [
            block for block in chapter.blocks if isinstance(block, Heading)
        ]
        if any(not heading.text.strip() for heading in headings):
            raise ExportError(
                "EPUB_HEADING_EMPTY", "Heading sem texto não pode compor a navegação."
            )
        values.extend(run.text for run in _runs(chapter))
    if any(not _is_xml_text(value) for value in values):
        raise ExportError("EPUB_XML_CHARACTER", "Texto contém caractere incompatível com XML 1.0.")


def _runs(chapter: Chapter) -> Iterable[Inline]:
    if chapter.heading:
        yield from chapter.heading.runs
    for block in chapter.blocks:
        yield from block.runs


def _is_xml_text(value: str) -> bool:
    return all(
        char in "\t\n\r"
        or "\x20" <= char <= "\ud7ff"
        or "\ue000" <= char <= "\ufffd"
        or "\U00010000" <= char <= "\U0010ffff"
        for char in value
    )


def _zip_info(name: str, compression: int = zipfile.ZIP_DEFLATED) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    info.compress_type = compression
    info.external_attr = 0o600 << 16
    return info


def _write_xml(epub: zipfile.ZipFile, name: str, root: ET.Element) -> None:
    with epub.open(_zip_info(name), "w") as target:
        ET.ElementTree(root).write(target, encoding="utf-8", xml_declaration=True)


def _container() -> ET.Element:
    root = ET.Element(f"{{{_CONTAINER_NS}}}container", {"version": "1.0"})
    rootfiles = ET.SubElement(root, f"{{{_CONTAINER_NS}}}rootfiles")
    ET.SubElement(
        rootfiles,
        f"{{{_CONTAINER_NS}}}rootfile",
        {"full-path": _OPF, "media-type": "application/oebps-package+xml"},
    )
    return root


def _package(
    document: SemanticDocument,
    chapters: tuple[tuple[str, ET.Element], ...],
    options: ExportOptions,
) -> ET.Element:
    root = ET.Element(
        f"{{{_OPF_NS}}}package",
        {
            "version": "3.0",
            "unique-identifier": "book-id",
            f"{{{_XML_NS}}}lang": document.metadata.language,
        },
    )
    metadata = ET.SubElement(root, f"{{{_OPF_NS}}}metadata")
    ET.SubElement(
        metadata, f"{{{_DC_NS}}}identifier", {"id": "book-id"}
    ).text = document.metadata.identifier
    ET.SubElement(metadata, f"{{{_DC_NS}}}title").text = document.metadata.title
    ET.SubElement(metadata, f"{{{_DC_NS}}}language").text = document.metadata.language
    if document.metadata.author is not None:
        ET.SubElement(metadata, f"{{{_DC_NS}}}creator").text = document.metadata.author
    modified = options.modified
    if modified.tzinfo is None:
        modified = modified.replace(tzinfo=UTC)
    modified = modified.astimezone(UTC).replace(microsecond=0)
    ET.SubElement(
        metadata, f"{{{_OPF_NS}}}meta", {"property": "dcterms:modified"}
    ).text = modified.strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = ET.SubElement(root, f"{{{_OPF_NS}}}manifest")
    ET.SubElement(
        manifest,
        f"{{{_OPF_NS}}}item",
        {
            "id": "nav",
            "href": "nav.xhtml",
            "media-type": "application/xhtml+xml",
            "properties": "nav",
        },
    )
    ET.SubElement(
        manifest,
        f"{{{_OPF_NS}}}item",
        {"id": "css", "href": "styles.css", "media-type": "text/css"},
    )
    for index, (name, _) in enumerate(chapters, 1):
        ET.SubElement(
            manifest,
            f"{{{_OPF_NS}}}item",
            {
                "id": f"chapter-{index}",
                "href": name.removeprefix("EPUB/"),
                "media-type": "application/xhtml+xml",
            },
        )
    spine = ET.SubElement(root, f"{{{_OPF_NS}}}spine")
    for index in range(1, len(chapters) + 1):
        ET.SubElement(spine, f"{{{_OPF_NS}}}itemref", {"idref": f"chapter-{index}"})
    return root


def _base_html(document: SemanticDocument, title: str) -> tuple[ET.Element, ET.Element]:
    root = ET.Element(
        f"{{{_XHTML_NS}}}html",
        {"lang": document.metadata.language, f"{{{_XML_NS}}}lang": document.metadata.language},
    )
    head = ET.SubElement(root, f"{{{_XHTML_NS}}}head")
    ET.SubElement(head, f"{{{_XHTML_NS}}}title").text = title
    ET.SubElement(head, f"{{{_XHTML_NS}}}link", {"rel": "stylesheet", "href": "styles.css"})
    return root, ET.SubElement(root, f"{{{_XHTML_NS}}}body")


def _content_path(index: int) -> str:
    return f"EPUB/chapter-{index:04d}.xhtml"


def _chapter(document: SemanticDocument, chapter: Chapter, index: int) -> tuple[str, ET.Element]:
    title = chapter.heading.text if chapter.heading else document.metadata.title
    root, body = _base_html(document, title)
    if chapter.heading:
        _heading(body, chapter.heading)
    for block in chapter.blocks:
        if isinstance(block, Heading):
            _heading(body, block)
        else:
            _paragraph(body, block)
    return _content_path(index), root


def _empty_content(document: SemanticDocument) -> ET.Element:
    root, _ = _base_html(document, document.metadata.title)
    return root


def _heading(parent: ET.Element, heading: Heading) -> None:
    element = ET.SubElement(parent, f"{{{_XHTML_NS}}}h{heading.level}", {"id": _anchor(heading.id)})
    _inline_content(element, heading.runs)


def _paragraph(parent: ET.Element, paragraph: Paragraph) -> None:
    element = ET.SubElement(parent, f"{{{_XHTML_NS}}}p", {"id": _anchor(paragraph.id)})
    _inline_content(element, paragraph.runs)


def _inline_content(parent: ET.Element, runs: tuple[Inline, ...]) -> None:
    for run in runs:
        target = parent
        if run.bold:
            target = ET.SubElement(target, f"{{{_XHTML_NS}}}strong")
        if run.italic:
            target = ET.SubElement(target, f"{{{_XHTML_NS}}}em")
        if target is parent:
            if len(parent):
                parent[-1].tail = (parent[-1].tail or "") + run.text
            else:
                parent.text = (parent.text or "") + run.text
        else:
            target.text = run.text


def _anchor(semantic_id: str) -> str:
    return "s-" + hashlib.sha256(semantic_id.encode()).hexdigest()[:24]


def _navigation(document: SemanticDocument, chapter_count: int) -> ET.Element:
    root, body = _base_html(document, document.metadata.title)
    nav = ET.SubElement(body, f"{{{_XHTML_NS}}}nav", {f"{{{_EPUB_NS}}}type": "toc"})
    ET.SubElement(nav, f"{{{_XHTML_NS}}}h1").text = document.metadata.title
    listing = ET.SubElement(nav, f"{{{_XHTML_NS}}}ol")
    for chapter_index in range(1, chapter_count + 1):
        chapter = document.chapters[chapter_index - 1] if document.chapters else None
        chapter_item = ET.SubElement(listing, f"{{{_XHTML_NS}}}li")
        chapter_heading = chapter.heading if chapter else None
        ET.SubElement(
            chapter_item,
            f"{{{_XHTML_NS}}}a",
            {
                "href": (
                    f"chapter-{chapter_index:04d}.xhtml#{_anchor(chapter_heading.id)}"
                    if chapter_heading
                    else f"chapter-{chapter_index:04d}.xhtml"
                )
            },
        ).text = chapter_heading.text if chapter_heading else document.metadata.title
        if chapter is None:
            continue
        headings = ([chapter.heading] if chapter.heading else []) + [
            block for block in chapter.blocks if isinstance(block, Heading)
        ]
        descendants = [heading for heading in headings if heading is not chapter_heading]
        if not descendants:
            continue
        child_list = ET.SubElement(chapter_item, f"{{{_XHTML_NS}}}ol")
        stack: list[tuple[int, ET.Element]] = []
        for position, heading in enumerate(descendants):
            while stack and stack[-1][0] >= heading.level:
                stack.pop()
            parent = stack[-1][1] if stack else child_list
            item = ET.SubElement(parent, f"{{{_XHTML_NS}}}li")
            ET.SubElement(
                item,
                f"{{{_XHTML_NS}}}a",
                {"href": f"chapter-{chapter_index:04d}.xhtml#{_anchor(heading.id)}"},
            ).text = heading.text
            stack.append((heading.level, item))
            next_heading = descendants[position + 1 : position + 2]
            if next_heading and next_heading[0].level > heading.level:
                stack[-1] = (
                    heading.level,
                    ET.SubElement(item, f"{{{_XHTML_NS}}}ol"),
                )
    return root
