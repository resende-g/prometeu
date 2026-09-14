"""Fronteira pública de inspeção, sem extração/reconstrução do documento."""

from dataclasses import dataclass
from pathlib import Path

from prometeu.application.metadata import resolve_metadata
from prometeu.document.contracts import ConversionLimits, ConversionRequest, DocumentKind, Severity
from prometeu.document.model import PDFMetadata
from prometeu.extraction import PdfPlumberExtractor


@dataclass(frozen=True, slots=True)
class DocumentInspection:
    file_name: str
    page_count: int
    kind: DocumentKind
    metadata: PDFMetadata
    warnings: tuple[str, ...]


def inspect_document(path: Path, limits: ConversionLimits | None = None) -> DocumentInspection:
    inspection = PdfPlumberExtractor().inspect(path, limits or ConversionLimits())
    # Não há hash/extração para inspeção; o identificador temporário não é exposto.
    metadata, diagnostics = resolve_metadata(
        ConversionRequest(path, identifier="urn:prometeu:inspection"), inspection.metadata, ""
    )
    return DocumentInspection(
        file_name=path.name,
        page_count=inspection.page_count,
        kind=inspection.kind,
        metadata=PDFMetadata(metadata.title, metadata.author, metadata.language),
        warnings=tuple(
            item.message
            for item in inspection.diagnostics + diagnostics
            if item.severity in {Severity.WARNING, Severity.ERROR}
        ),
    )
