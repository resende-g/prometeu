"""Primeira reconstrução: ordem física e parágrafos por distância vertical."""

from collections.abc import Mapping
from statistics import median_low

from prometeu.document.contracts import ReconstructionResult
from prometeu.document.model import (
    Chapter,
    Heading,
    Inline,
    Metadata,
    Paragraph,
    PhysicalDocument,
    PhysicalLine,
    SemanticDocument,
    SourceReference,
)


class ParagraphReconstructor:
    def reconstruct(
        self, lines: tuple[PhysicalLine, ...], page_heights: Mapping[int, float] | None = None
    ) -> tuple[Paragraph, ...]:
        groups: list[list[PhysicalLine]] = []
        for line in lines:
            if not line.text.strip():
                continue
            previous = groups[-1][-1] if groups else None
            new_paragraph = previous is None or previous.page != line.page
            if previous is not None and previous.page == line.page:
                height = max(previous.bbox.bottom - previous.bbox.top, 1.0)
                new_paragraph = (
                    line.bbox.top - previous.bbox.bottom > height * 0.8
                    or line.bbox.top < previous.bbox.top
                    or abs(line.bbox.x0 - previous.bbox.x0) > height * 0.8
                    or not _same_style(previous, line)
                )
            elif previous is not None and page_heights:
                # ponytail: uma coluna; layouts complexos exigem segmentação no Gate C.
                new_paragraph = not (
                    line.page == previous.page + 1
                    and previous.bbox.bottom >= page_heights[previous.page] * 0.8
                    and line.bbox.top <= page_heights[line.page] * 0.2
                    and previous.text.rstrip()[-1] not in ".!?…:;"
                    and line.text.lstrip()[0].islower()
                    and abs(line.bbox.x0 - previous.bbox.x0) <= 12
                    and _same_style(previous, line)
                )
            if new_paragraph:
                groups.append([])
            groups[-1].append(line)
        paragraphs = []
        for group in groups:
            runs: list[Inline] = []
            for index, line in enumerate(group):
                if index:
                    runs.append(
                        Inline(
                            "\n",
                            source=SourceReference(
                                group[index - 1].source.lines + line.source.lines
                            ),
                        )
                    )
                runs.extend(
                    Inline(span.text, span.style.bold, span.style.italic, line.source)
                    for span in line.spans
                )
            paragraphs.append(
                Paragraph(
                    f"para-{group[0].id}",
                    tuple(runs),
                    SourceReference(
                        tuple(origin for line in group for origin in line.source.lines)
                    ),
                )
            )
        return tuple(paragraphs)


def _same_style(previous: PhysicalLine, line: PhysicalLine) -> bool:
    if not previous.spans or not line.spans:
        return False
    left, right = previous.spans[-1].style, line.spans[0].style
    return abs(left.size - right.size) <= min(left.size, right.size) * 0.1 and (
        left.bold,
        left.italic,
    ) == (right.bold, right.italic)


def _chapter(heading: Heading | None, blocks: list[Paragraph]) -> Chapter:
    source = heading.source if heading else blocks[0].source if blocks else SourceReference()
    suffix = source.lines[0].line_id if source.lines else "1"
    return Chapter(f"chapter-{suffix}", heading, tuple(blocks))


def reconstruct(physical: PhysicalDocument, metadata: Metadata) -> ReconstructionResult:
    lines = tuple(line for page in physical.pages for line in page.lines)
    paragraphs = ParagraphReconstructor().reconstruct(
        lines, {page.number: page.height for page in physical.pages}
    )
    styles = [span.style for line in lines for span in line.spans if span.text.strip()]
    body_sizes = [style.size for style in styles if not style.bold]
    body_size = median_low(body_sizes or [style.size for style in styles]) if styles else 12.0
    lines_by_id = {line.id: line for line in lines}
    chapters: list[Chapter] = []
    heading: Heading | None = None
    blocks: list[Paragraph] = []
    for paragraph in paragraphs:
        origin = paragraph.source.lines
        line = lines_by_id[origin[0].line_id] if len(origin) == 1 else None
        styles = [span.style for span in line.spans if span.text.strip()] if line else []
        is_heading = (
            bool(styles)
            and all(style.bold for style in styles)
            and min(style.size for style in styles) > body_size * 1.3
        )
        if not is_heading:
            blocks.append(paragraph)
            continue
        if heading is not None or blocks:
            chapters.append(_chapter(heading, blocks))
        heading = Heading(
            paragraph.id.replace("para-", "heading-", 1),
            1,
            paragraph.runs,
            paragraph.source,
            0.9,
            ("single-line", "bold", "font-size"),
        )
        blocks = []
    chapters.append(_chapter(heading, blocks))
    return ReconstructionResult(
        SemanticDocument(
            physical.id,
            metadata,
            tuple(chapters),
        )
    )
