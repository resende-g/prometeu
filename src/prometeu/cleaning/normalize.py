import re
from dataclasses import replace

from prometeu.document.contracts import ExportError, NormalizationResult
from prometeu.document.model import Block, Inline, PhysicalDocument, SemanticDocument


def xml_text_valid(text: str) -> bool:
    return all(
        char in "\t\n\r"
        or 0x20 <= ord(char) <= 0xD7FF
        or 0xE000 <= ord(char) <= 0xFFFD
        or 0x10000 <= ord(char) <= 0x10FFFF
        for char in text
    )


def _normalize_runs(original: tuple[Inline, ...]) -> tuple[Inline, ...]:
    runs: list[Inline] = []
    previous_space = True
    for run in original:
        if not xml_text_valid(run.text):
            raise ExportError("XML_CHARACTER", "Texto contém caractere incompatível com XML 1.0.")
        text = re.sub(r"[ \t\r\n]+", " ", run.text)
        if previous_space:
            text = text.lstrip(" ")
        if text:
            previous_space = text.endswith(" ")
            runs.append(replace(run, text=text))
    if runs:
        runs[-1] = replace(runs[-1], text=runs[-1].text.rstrip(" "))
    return tuple(run for run in runs if run.text)


def normalize_block(block: Block) -> Block:
    return replace(block, runs=_normalize_runs(block.runs))


def normalize(document: SemanticDocument, physical: PhysicalDocument) -> NormalizationResult:
    """Evidence is explicit; baseline changes only ASCII layout whitespace."""
    chapters = tuple(
        replace(
            chapter,
            heading=replace(chapter.heading, runs=_normalize_runs(chapter.heading.runs))
            if chapter.heading
            else None,
            blocks=tuple(normalize_block(b) for b in chapter.blocks),
        )
        for chapter in document.chapters
    )
    return NormalizationResult(replace(document, chapters=chapters))
