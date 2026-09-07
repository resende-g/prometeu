"""Valores imutáveis, sem objetos de bibliotecas PDF ou markup de exportação.

Coordenadas em pontos (1/72 polegada), origem superior esquerda, x à direita,
y para baixo; páginas a partir de 1. Texto de spans físicos nunca é normalizado.
"""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class BoundingBox:
    x0: float
    top: float
    x1: float
    bottom: float

    def __post_init__(self) -> None:
        if not all(isfinite(v) for v in (self.x0, self.top, self.x1, self.bottom)):
            raise ValueError("Coordenadas devem ser finitas.")
        if self.x1 < self.x0 or self.bottom < self.top:
            raise ValueError("Bounding box invertida.")


@dataclass(frozen=True, slots=True)
class TextStyle:
    font_name: str = ""
    size: float = 12.0
    bold: bool = False
    italic: bool = False

    def __post_init__(self) -> None:
        if not isfinite(self.size) or self.size <= 0:
            raise ValueError("Tamanho de fonte deve ser positivo e finito.")


@dataclass(frozen=True, slots=True)
class LineOrigin:
    page: int
    line_id: str

    def __post_init__(self) -> None:
        if self.page < 1 or not self.line_id:
            raise ValueError("Origem exige página positiva e ID de linha.")


@dataclass(frozen=True, slots=True)
class SourceReference:
    lines: tuple[LineOrigin, ...] = ()


@dataclass(frozen=True, slots=True)
class PhysicalSpan:
    id: str
    text: str
    bbox: BoundingBox
    style: TextStyle


@dataclass(frozen=True, slots=True)
class PhysicalLine:
    id: str
    page: int
    bbox: BoundingBox
    spans: tuple[PhysicalSpan, ...]

    def __post_init__(self) -> None:
        if self.page < 1 or not self.id:
            raise ValueError("Linha exige página positiva e ID.")

    @property
    def text(self) -> str:
        return "".join(span.text for span in self.spans)

    @property
    def source(self) -> SourceReference:
        return SourceReference((LineOrigin(self.page, self.id),))


@dataclass(frozen=True, slots=True)
class PhysicalPage:
    number: int
    width: float
    height: float
    lines: tuple[PhysicalLine, ...]
    image_count: int = 0
    has_visual_content: bool = False

    def __post_init__(self) -> None:
        if self.number < 1 or not all(isfinite(v) and v > 0 for v in (self.width, self.height)):
            raise ValueError("Página exige número e dimensões positivos e finitos.")
        if any(line.page != self.number for line in self.lines):
            raise ValueError("Proveniência da linha não corresponde à página.")
        if len({line.id for line in self.lines}) != len(self.lines):
            raise ValueError("IDs de linha repetidos.")


@dataclass(frozen=True, slots=True)
class PDFMetadata:
    title: str | None = None
    author: str | None = None
    language: str | None = None


@dataclass(frozen=True, slots=True)
class PhysicalDocument:
    id: str
    pages: tuple[PhysicalPage, ...]
    metadata: PDFMetadata = PDFMetadata()

    def __post_init__(self) -> None:
        if tuple(p.number for p in self.pages) != tuple(range(1, len(self.pages) + 1)):
            raise ValueError("Páginas devem ser consecutivas, a partir de 1.")
        ids = [line.id for p in self.pages for line in p.lines]
        if len(set(ids)) != len(ids):
            raise ValueError("IDs físicos devem ser únicos no documento.")


@dataclass(frozen=True, slots=True)
class Metadata:
    title: str
    identifier: str
    language: str = "und"
    author: str | None = None


@dataclass(frozen=True, slots=True)
class Inline:
    text: str
    bold: bool = False
    italic: bool = False
    source: SourceReference = SourceReference()


@dataclass(frozen=True, slots=True)
class Paragraph:
    id: str
    runs: tuple[Inline, ...]
    source: SourceReference = SourceReference()

    @property
    def text(self) -> str:
        return "".join(run.text for run in self.runs)


@dataclass(frozen=True, slots=True)
class Heading:
    id: str
    level: int
    runs: tuple[Inline, ...]
    source: SourceReference = SourceReference()
    confidence: float = 1.0
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.level not in (1, 2, 3):
            raise ValueError("Heading exige nível 1–3.")
        if not isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("Confidence heurística deve estar entre 0 e 1.")

    @property
    def text(self) -> str:
        return "".join(run.text for run in self.runs)


Block = Heading | Paragraph


@dataclass(frozen=True, slots=True)
class Chapter:
    id: str
    heading: Heading | None
    blocks: tuple[Block, ...]

    def __post_init__(self) -> None:
        if self.heading is not None and self.heading.level != 1:
            raise ValueError("Título de capítulo deve ser H1.")
        if any(isinstance(block, Heading) and block.level == 1 for block in self.blocks):
            raise ValueError("H1 pertence a Chapter.heading, nunca aos blocks.")


@dataclass(frozen=True, slots=True)
class SemanticDocument:
    id: str
    metadata: Metadata
    chapters: tuple[Chapter, ...]

    def __post_init__(self) -> None:
        ids: list[str] = []
        for chapter in self.chapters:
            ids.append(chapter.id)
            if chapter.heading:
                ids.append(chapter.heading.id)
            ids.extend(block.id for block in chapter.blocks)
        if len(set(ids)) != len(ids) or any(not value for value in ids):
            raise ValueError("IDs semânticos devem ser não vazios e únicos.")
