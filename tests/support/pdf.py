"""Gerador PDF sintético, determinístico e sem dependências externas.

As coordenadas usam a convenção nativa do PDF: origem inferior esquerda.
O ``ToUnicode`` preserva o texto extraído; sem fonte incorporada, caracteres fora
de WinAnsi não têm garantia de renderização visual.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

PAGE_WIDTH = 595
PAGE_HEIGHT = 842


@dataclass(frozen=True, slots=True)
class TextLine:
    text: str
    x: float
    y: float
    size: float = 12.0
    bold: bool = False


def _stream(data: bytes) -> bytes:
    return b"<< /Length %d >>\nstream\n" % len(data) + data + b"\nendstream"


def _hex_text(value: str) -> bytes:
    return (b"\xfe\xff" + value.encode("utf-16-be")).hex().upper().encode("ascii")


def _to_unicode(codes: Mapping[str, int]) -> bytes:
    mappings = [
        f"<{code:02X}> <{character.encode('utf-16-be').hex().upper()}>"
        for character, code in codes.items()
    ]
    sections = []
    for start in range(0, len(mappings), 100):
        chunk = mappings[start : start + 100]
        sections.extend((f"{len(chunk)} beginbfchar", *chunk, "endbfchar"))
    return (
        "/CIDInit /ProcSet findresource begin\n"
        "12 dict begin\n"
        "begincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        "/CMapName /Prometeu-ToUnicode def\n"
        "/CMapType 2 def\n"
        "1 begincodespacerange\n<01> <FF>\nendcodespacerange\n"
        + "\n".join(sections)
        + "\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend"
    ).encode("ascii")


def write_pdf(
    path: Path,
    pages: Sequence[Sequence[TextLine]],
    metadata: Mapping[str, str] | None = None,
) -> Path:
    """Escreve um PDF 1.4 A4; aceita até 255 caracteres distintos."""
    characters = dict.fromkeys(
        character for page in pages for line in page for character in line.text
    )
    if len(characters) > 255:
        raise ValueError("O gerador sintético aceita até 255 caracteres distintos.")
    codes = {character: index for index, character in enumerate(characters, 1)}

    objects: list[bytes] = [b"", b""]
    page_refs: list[int] = []
    content_refs: list[int] = []
    for page in pages:
        page_refs.append(len(objects) + 1)
        objects.append(b"")
        content_refs.append(len(objects) + 1)
        commands = []
        for line in page:
            encoded = bytes(codes[character] for character in line.text).hex().upper()
            font = "F2" if line.bold else "F1"
            commands.append(
                f"BT /{font} {line.size:g} Tf 1 0 0 1 {line.x:g} {line.y:g} Tm <{encoded}> Tj ET"
            )
        objects.append(_stream("\n".join(commands).encode("ascii")))

    regular_font_ref = len(objects) + 1
    objects.append(b"")
    bold_font_ref = len(objects) + 1
    objects.append(b"")
    cmap_ref = len(objects) + 1
    objects.append(_stream(_to_unicode(codes)))
    info_ref = len(objects) + 1
    info = metadata or {}
    allowed_metadata = {"Title", "Author", "Subject", "Keywords", "Creator", "Producer"}
    if unknown := set(info) - allowed_metadata:
        raise ValueError(f"Metadados PDF não suportados: {', '.join(sorted(unknown))}")
    objects.append(
        b"<< "
        + b" ".join(
            f"/{key} <".encode("ascii") + _hex_text(value) + b">" for key, value in info.items()
        )
        + b" >>"
    )

    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{ref} 0 R" for ref in page_refs)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_refs)} >>".encode("ascii")
    for page_ref, content_ref in zip(page_refs, content_refs, strict=True):
        objects[page_ref - 1] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 {regular_font_ref} 0 R /F2 {bold_font_ref} 0 R >> >> "
            f"/Contents {content_ref} 0 R >>"
        ).encode("ascii")
    objects[regular_font_ref - 1] = (
        f"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding "
        f"/ToUnicode {cmap_ref} 0 R >>"
    ).encode("ascii")
    objects[bold_font_ref - 1] = (
        f"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding "
        f"/ToUnicode {cmap_ref} 0 R >>"
    ).encode("ascii")

    document = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\x00\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(document))
        document.extend(f"{number} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    document.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info {info_ref} 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    path.write_bytes(document)
    return path
