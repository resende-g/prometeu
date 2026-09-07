"""Contratos mínimos compartilhados; nenhum import de adapter, CLI ou builder."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from pathlib import Path
from typing import Protocol

from prometeu.document.model import PDFMetadata, PhysicalDocument, SemanticDocument, SourceReference


class Severity(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str
    severity: Severity = Severity.WARNING
    source: SourceReference = SourceReference()
    count: int = 1


@dataclass(frozen=True, slots=True)
class ConversionLimits:
    max_input_bytes: int = 50 * 1024 * 1024
    max_pages: int = 500
    max_characters: int = 5_000_000
    max_output_bytes: int = 50 * 1024 * 1024
    timeout_seconds: float = 120.0
    memory_bytes: int = 1024 * 1024 * 1024
    cpu_seconds: int = 120

    def __post_init__(self) -> None:
        values = (
            self.max_input_bytes,
            self.max_pages,
            self.max_characters,
            self.max_output_bytes,
            self.timeout_seconds,
            self.memory_bytes,
            self.cpu_seconds,
        )
        if not all(isfinite(v) and v > 0 for v in values):
            raise ValueError("Todos os limites devem ser positivos e finitos.")


class DocumentKind(StrEnum):
    TEXTUAL = "textual"
    SCANNED = "scanned"
    MIXED = "mixed"
    EMPTY = "empty"


@dataclass(frozen=True, slots=True)
class InspectionResult:
    kind: DocumentKind
    page_count: int
    text_pages: tuple[int, ...]
    visual_only_pages: tuple[int, ...]
    blank_pages: tuple[int, ...]
    metadata: PDFMetadata = PDFMetadata()
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class ConversionRequest:
    input_path: Path
    output_path: Path | None = None
    title: str | None = None
    author: str | None = None
    language: str | None = None
    identifier: str | None = None
    overwrite: bool = False
    limits: ConversionLimits = ConversionLimits()
    epubcheck: Path | None = None
    require_epubcheck: bool = False


@dataclass(frozen=True, slots=True)
class ExportOptions:
    modified: datetime
    max_output_bytes: int = 50 * 1024 * 1024


class ValidationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_RUN = "not_run"


@dataclass(frozen=True, slots=True)
class ValidationResult:
    name: str
    status: ValidationStatus
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class DocumentStatistics:
    pages: int = 0
    physical_lines: int = 0
    extracted_characters: int = 0
    paragraphs: int = 0
    headings: int = 0
    chapters: int = 0
    removed_lines: int = 0
    dehyphenations: int = 0
    output_bytes: int = 0


@dataclass(frozen=True, slots=True)
class ConversionResult:
    success: bool
    published_path: Path | None = None
    diagnostics: tuple[Diagnostic, ...] = ()
    statistics: DocumentStatistics = DocumentStatistics()
    validations: tuple[ValidationResult, ...] = ()
    exit_code: int = 0

    def __post_init__(self) -> None:
        if self.success != (self.published_path is not None and self.exit_code == 0):
            raise ValueError("Resultado inconsistente com publicação e código de saída.")


@dataclass(frozen=True, slots=True)
class ReconstructionResult:
    document: SemanticDocument
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    document: SemanticDocument
    diagnostics: tuple[Diagnostic, ...] = ()
    removed_lines: int = 0
    dehyphenations: int = 0


class PrometeuError(Exception):
    exit_code = 1

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class InputError(PrometeuError):
    exit_code = 2


class UnsupportedDocumentError(PrometeuError):
    exit_code = 3


class ExtractionError(PrometeuError):
    exit_code = 4


class ExportError(PrometeuError):
    exit_code = 5


class ValidationError(PrometeuError):
    exit_code = 6


class PDFExtractor(Protocol):
    def inspect(self, path: Path, limits: ConversionLimits) -> InspectionResult: ...

    def extract(
        self, path: Path, inspection: InspectionResult, limits: ConversionLimits
    ) -> PhysicalDocument: ...


class EPUBExporter(Protocol):
    def export(self, document: SemanticDocument, path: Path, options: ExportOptions) -> None: ...


class EPUBValidator(Protocol):
    def validate(self, path: Path, limits: ConversionLimits) -> ValidationResult: ...
