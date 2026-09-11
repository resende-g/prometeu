"""Primeira reconstrução: ordem física e parágrafos por distância vertical."""

from collections.abc import Mapping

from prometeu.cleaning.normalize import body_font_size, pagination_origins
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
        self,
        lines: tuple[PhysicalLine, ...],
        page_heights: Mapping[int, float] | None = None,
        separate_line_ids: set[str] | None = None,
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
            if (
                previous is not None
                and separate_line_ids
                and (previous.id in separate_line_ids or line.id in separate_line_ids)
            ):
                new_paragraph = True
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


def _chapter(heading: Heading | None, blocks: list[Heading | Paragraph]) -> Chapter:
    source = heading.source if heading else blocks[0].source if blocks else SourceReference()
    suffix = source.lines[0].line_id if source.lines else "1"
    return Chapter(f"chapter-{suffix}", heading, tuple(blocks))


def _ignored_marginal_lines(physical: PhysicalDocument) -> set[str]:
    repeated: dict[tuple[str, str], list[PhysicalLine]] = {}
    ignored = {line_id for _, line_id in pagination_origins(physical)}
    for page in physical.pages:
        for line in page.lines:
            margin = (
                "header"
                if line.bbox.bottom <= page.height * 0.1
                else "footer"
                if line.bbox.top >= page.height * 0.9
                else None
            )
            if margin is None:
                continue
            text = " ".join(line.text.split())
            if not text:
                continue
            repeated.setdefault((margin, text.casefold()), []).append(line)
    for occurrences in repeated.values():
        if len({line.page for line in occurrences}) > 1:
            ignored.update(line.id for line in occurrences)
    return ignored


def _heading_levels(
    lines: tuple[PhysicalLine, ...],
    body_size: float,
    single_line_ids: set[str],
    ignored: set[str],
) -> dict[str, int]:
    sizes: dict[str, float] = {}
    for line in lines:
        styles = [span.style for span in line.spans if span.text.strip()]
        if (
            line.id in single_line_ids
            and line.id not in ignored
            and styles
            and all(style.bold for style in styles)
            and min(style.size for style in styles) > body_size * 1.05
        ):
            sizes[line.id] = round(min(style.size for style in styles), 2)
    if not sizes:
        return {}
    tiers = sorted(set(sizes.values()), reverse=True)
    first_level = 1 if tiers[0] > body_size * 1.3 else 2
    levels = dict(zip(tiers, range(first_level, 4), strict=False))
    return {line_id: levels[size] for line_id, size in sizes.items() if size in levels}


def reconstruct(physical: PhysicalDocument, metadata: Metadata) -> ReconstructionResult:
    lines = tuple(line for page in physical.pages for line in page.lines)
    ignored = _ignored_marginal_lines(physical)
    paragraphs = ParagraphReconstructor().reconstruct(
        lines, {page.number: page.height for page in physical.pages}, ignored
    )
    body_size = body_font_size(physical)
    lines_by_id = {line.id: line for line in lines}
    single_line_ids = {
        paragraph.source.lines[0].line_id
        for paragraph in paragraphs
        if len(paragraph.source.lines) == 1
    }
    heading_levels = _heading_levels(lines, body_size, single_line_ids, ignored)
    chapters: list[Chapter] = []
    heading: Heading | None = None
    blocks: list[Heading | Paragraph] = []
    for paragraph in paragraphs:
        origin = paragraph.source.lines
        line = lines_by_id[origin[0].line_id] if len(origin) == 1 else None
        level = heading_levels.get(line.id) if line else None
        if level is None:
            blocks.append(paragraph)
            continue
        semantic_heading = Heading(
            paragraph.id.replace("para-", "heading-", 1),
            level,
            paragraph.runs,
            paragraph.source,
            0.9,
            ("single-line", "bold", "font-size", "font-rank"),
        )
        if level != 1:
            blocks.append(semantic_heading)
            continue
        if heading is not None or blocks:
            chapters.append(_chapter(heading, blocks))
        heading = semantic_heading
        blocks = []
    chapters.append(_chapter(heading, blocks))
    return ReconstructionResult(
        SemanticDocument(
            physical.id,
            metadata,
            tuple(chapters),
        )
    )
