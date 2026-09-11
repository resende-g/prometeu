import re
import unicodedata
from dataclasses import replace
from statistics import median_low
from typing import cast

from prometeu.document.contracts import ExportError, NormalizationResult
from prometeu.document.model import (
    Block,
    Heading,
    Inline,
    Paragraph,
    PhysicalDocument,
    SemanticDocument,
)


def xml_text_valid(text: str) -> bool:
    return all(
        char in "\t\n\r"
        or 0x20 <= ord(char) <= 0xD7FF
        or 0xE000 <= ord(char) <= 0xFFFD
        or 0x10000 <= ord(char) <= 0x10FFFF
        for char in text
    )


def body_font_size(physical: PhysicalDocument) -> float:
    styles = [
        span.style
        for page in physical.pages
        for line in page.lines
        for span in line.spans
        if span.text.strip()
    ]
    body_sizes = [style.size for style in styles if not style.bold]
    return median_low(body_sizes or [style.size for style in styles]) if styles else 12.0


def pagination_origins(physical: PhysicalDocument) -> set[tuple[int, str]]:
    candidates: list[tuple[tuple[int, str], int, int]] = []
    body_size = body_font_size(physical)
    for page in physical.pages:
        for line in page.lines:
            if line.bbox.bottom > page.height * 0.1 and line.bbox.top < page.height * 0.9:
                continue
            text = line.text.strip()
            styles = [span.style for span in line.spans if span.text.strip()]
            if (
                text.isdecimal()
                and line.bbox.bottom <= page.height * 0.1
                and styles
                and all(style.bold for style in styles)
                and min(style.size for style in styles) > body_size * 1.3
            ):
                continue
            match = re.fullmatch(
                r"(?:(?P<mark>[-–—])\s*(?P<marked>\d+)\s*(?P=mark)"
                r"|\[(?P<bracketed>\d+)\]|página\s+(?P<labelled>\d+))",
                text,
                flags=re.IGNORECASE,
            )
            number = (
                int(text)
                if text.isdecimal()
                else (
                    int(match["marked"] or match["bracketed"] or match["labelled"]) if match else 0
                )
            )
            if number > 0:
                candidates.append(((page.number, line.id), page.number, number))
    sequences: dict[int, set[int]] = {}
    for _, page_number, number in candidates:
        sequences.setdefault(number - page_number, set()).add(page_number)
    return {
        origin
        for origin, page_number, number in candidates
        if len(sequences[number - page_number]) > 1
    }


def _normalize_runs(
    original: tuple[Inline, ...], confirmed_breaks: set[tuple[int, str, int, str]]
) -> tuple[tuple[Inline, ...], int]:
    runs: list[Inline] = []
    previous_space = True
    dehyphenations = 0
    for index, run in enumerate(original):
        if not xml_text_valid(run.text):
            raise ExportError("XML_CHARACTER", "Texto contém caractere incompatível com XML 1.0.")
        origins = run.source.lines
        if (
            run.text == "\n"
            and len(origins) == 2
            and (origins[0].page, origins[0].line_id, origins[1].page, origins[1].line_id)
            in confirmed_breaks
            and runs
            and index + 1 < len(original)
            and runs[-1].source.lines == (origins[0],)
            and original[index + 1].source.lines == (origins[1],)
        ):
            text = runs[-1].text.rstrip(" \t\r")
            if text.endswith("-"):
                runs[-1] = replace(runs[-1], text=text[:-1])
                previous_space = False
                dehyphenations += 1
                continue
        text = unicodedata.normalize("NFC", re.sub(r"[ \t\r\n]+", " ", run.text))
        if previous_space:
            text = text.lstrip(" ")
        if text:
            previous_space = text.endswith(" ")
            runs.append(replace(run, text=text))
    if runs:
        runs[-1] = replace(runs[-1], text=runs[-1].text.rstrip(" "))
    return tuple(run for run in runs if run.text), dehyphenations


def normalize(document: SemanticDocument, physical: PhysicalDocument) -> NormalizationResult:
    """Normaliza whitespace e remove paginação ou texto marginal recorrente."""
    lines = tuple(line for page in physical.pages for line in page.lines)
    words = {
        word.casefold()
        for line in lines
        for word in re.findall(r"[^\W\d_]+", line.text, flags=re.UNICODE)
    }
    hyphenated = {
        word.casefold()
        for line in lines
        for word in re.findall(r"[^\W\d_]+-[^\W\d_]+", line.text, flags=re.UNICODE)
    }
    confirmed_breaks: set[tuple[int, str, int, str]] = set()
    for left, right in zip(lines, lines[1:], strict=False):
        prefix = re.search(r"([^\W\d_]+)-\s*$", left.text, flags=re.UNICODE)
        suffix = re.match(r"\s*([^\W\d_]+)", right.text, flags=re.UNICODE)
        if (
            prefix
            and suffix
            and suffix[1][0].islower()
            and (prefix[1] + suffix[1]).casefold() in words
            and (prefix[1] + "-" + suffix[1]).casefold() not in hyphenated
        ):
            confirmed_breaks.add((left.page, left.id, right.page, right.id))
    pagination = pagination_origins(physical)
    marginal: dict[tuple[str, str], set[tuple[int, str]]] = {}
    for page in physical.pages:
        for line in page.lines:
            margin = (
                "header"
                if line.bbox.bottom <= page.height * 0.1
                else "footer"
                if line.bbox.top >= page.height * 0.9
                else None
            )
            text = " ".join(line.text.split()).casefold()
            if margin and text:
                marginal.setdefault((margin, text), set()).add((page.number, line.id))
    repeated = {
        origin
        for occurrences in marginal.values()
        if len({page for page, _ in occurrences}) > 1
        for origin in occurrences
    }
    removable = pagination | repeated
    removed: set[tuple[int, str]] = set()
    dehyphenations = 0

    def keep(block: Block) -> bool:
        origins = {(origin.page, origin.line_id) for origin in block.source.lines}
        if isinstance(block, Paragraph) and origins and origins <= removable:
            removed.update(origins)
            return False
        return True

    def normalized(block: Block) -> Block:
        nonlocal dehyphenations
        runs, count = _normalize_runs(block.runs, confirmed_breaks)
        dehyphenations += count
        return replace(block, runs=runs)

    chapters = tuple(
        replace(
            chapter,
            heading=cast(Heading, normalized(chapter.heading)) if chapter.heading else None,
            blocks=tuple(normalized(block) for block in chapter.blocks if keep(block)),
        )
        for chapter in document.chapters
    )
    nonempty_chapters = tuple(chapter for chapter in chapters if chapter.heading or chapter.blocks)
    return NormalizationResult(
        replace(document, chapters=nonempty_chapters or chapters[:1]),
        removed_lines=len(removed),
        dehyphenations=dehyphenations,
    )
