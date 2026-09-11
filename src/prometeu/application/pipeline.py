"""Pipeline local: snapshot → dois modelos → EPUB validado → publicação."""

import os
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from prometeu.application.metadata import resolve_metadata
from prometeu.application.safety import (
    check_destination,
    deadline,
    open_input,
    output_directory,
    publish,
    remaining,
    snapshot,
)
from prometeu.cleaning.normalize import normalize
from prometeu.document.contracts import (
    ConversionRequest,
    ConversionResult,
    Diagnostic,
    DocumentKind,
    DocumentStatistics,
    EPUBExporter,
    EPUBValidator,
    ExportError,
    ExportOptions,
    InputError,
    PDFExtractor,
    PrometeuError,
    Severity,
    UnsupportedDocumentError,
    ValidationError,
    ValidationResult,
    ValidationStatus,
)
from prometeu.document.model import Heading, Paragraph
from prometeu.epub.builder import EPUBBuilder
from prometeu.extraction.pdfplumber_adapter import PdfPlumberExtractor
from prometeu.structure.reconstruct import reconstruct
from prometeu.validation.internal import InternalEPUBValidator


class ConversionPipeline:
    def __init__(
        self,
        extractor: PDFExtractor | None = None,
        exporter: EPUBExporter | None = None,
        validator: EPUBValidator | None = None,
    ) -> None:
        self.extractor = extractor if extractor is not None else PdfPlumberExtractor()
        self.exporter = exporter if exporter is not None else EPUBBuilder()
        self.validator = validator if validator is not None else InternalEPUBValidator()

    def run(self, request: ConversionRequest) -> ConversionResult:
        diagnostics: list[Diagnostic] = []
        validations = [
            ValidationResult("internal", ValidationStatus.NOT_RUN),
            ValidationResult("epubcheck", ValidationStatus.NOT_RUN),
        ]
        statistics = DocumentStatistics()
        started = time.monotonic()
        try:
            if request.require_epubcheck:
                raise ValidationError(
                    "EPUBCHECK_NOT_RUN", "EPUBCheck obrigatório ainda não é suportado nesta etapa."
                )
            if request.epubcheck is not None:
                diagnostics.append(
                    Diagnostic("EPUBCHECK_NOT_RUN", "EPUBCheck não executado nesta etapa.")
                )
            output = request.output_path or request.input_path.with_suffix(".epub")
            with open_input(request.input_path, request.limits) as input_fd:
                with output_directory(output, request.input_path) as (target, directory_fd):
                    expected = check_destination(
                        target.name, directory_fd, input_fd, request.overwrite
                    )
                    with TemporaryDirectory(
                        prefix=".prometeu-", dir=target.parent, ignore_cleanup_errors=True
                    ) as workspace:
                        working = Path(workspace)
                        source, temporary = working / "input.pdf", working / "output.epub"
                        with deadline(remaining(started, request.limits)):
                            digest = snapshot(input_fd, source, request.limits)
                            inspection = self.extractor.inspect(
                                source,
                                replace(
                                    request.limits,
                                    timeout_seconds=remaining(started, request.limits),
                                ),
                            )
                            diagnostics.extend(inspection.diagnostics)
                            if inspection.visual_only_pages or inspection.kind in (
                                DocumentKind.SCANNED,
                                DocumentKind.MIXED,
                            ):
                                raise UnsupportedDocumentError(
                                    "PDF_VISUAL_ONLY_CONTENT",
                                    "Conteúdo visual não extraível; OCR indisponível.",
                                )
                            if inspection.kind is DocumentKind.EMPTY:
                                raise UnsupportedDocumentError(
                                    "PDF_EMPTY", "PDF não contém texto extraível."
                                )
                            physical = self.extractor.extract(
                                source,
                                inspection,
                                replace(
                                    request.limits,
                                    timeout_seconds=remaining(started, request.limits),
                                ),
                            )
                            lines = tuple(line for page in physical.pages for line in page.lines)
                            if not any(line.text.strip() for line in lines):
                                raise UnsupportedDocumentError(
                                    "PDF_EMPTY", "Extração não contém texto utilizável."
                                )
                            statistics = replace(
                                statistics,
                                pages=len(physical.pages),
                                physical_lines=len(lines),
                                extracted_characters=sum(len(line.text) for line in lines),
                            )
                            metadata, metadata_diagnostics = resolve_metadata(
                                request, physical.metadata, digest, physical
                            )
                            diagnostics.extend(metadata_diagnostics)
                            reconstruction = reconstruct(physical, metadata)
                            diagnostics.extend(reconstruction.diagnostics)
                            normalization = normalize(reconstruction.document, physical)
                            semantic = normalization.document
                            diagnostics.extend(normalization.diagnostics)
                            statistics = replace(
                                statistics,
                                chapters=len(semantic.chapters),
                                paragraphs=sum(
                                    isinstance(b, Paragraph)
                                    for c in semantic.chapters
                                    for b in c.blocks
                                ),
                                headings=sum(
                                    int(c.heading is not None)
                                    + sum(isinstance(b, Heading) for b in c.blocks)
                                    for c in semantic.chapters
                                ),
                                removed_lines=normalization.removed_lines,
                                dehyphenations=normalization.dehyphenations,
                            )
                            self.exporter.export(
                                semantic,
                                temporary,
                                ExportOptions(datetime.now(UTC), request.limits.max_output_bytes),
                            )
                            try:
                                output_bytes = temporary.stat().st_size
                            except OSError as error:
                                raise ExportError(
                                    "EPUB_NOT_CREATED", "Exportador não produziu EPUB acessível."
                                ) from error
                            if not 0 < output_bytes <= request.limits.max_output_bytes:
                                raise ExportError(
                                    "EPUB_OUTPUT_LIMIT", "EPUB vazio ou acima do limite de saída."
                                )
                            validations[0] = self.validator.validate(temporary, request.limits)
                            diagnostics.extend(validations[0].diagnostics)
                            if validations[0].status is not ValidationStatus.PASSED:
                                raise ValidationError(
                                    "EPUB_VALIDATION_FAILED",
                                    "EPUB temporário não aprovado; saída preservada.",
                                )
                            with temporary.open("rb") as stream:
                                os.fsync(stream.fileno())
                            remaining(started, request.limits)
                            current_directory = target.parent.stat()
                            pinned_directory = os.fstat(directory_fd)
                            if (current_directory.st_dev, current_directory.st_ino) != (
                                pinned_directory.st_dev,
                                pinned_directory.st_ino,
                            ):
                                raise InputError(
                                    "OUTPUT_DIRECTORY_CHANGED",
                                    "Diretório de saída alterado; publicação cancelada.",
                                )
                            statistics = replace(statistics, output_bytes=output_bytes)
                        # O prazo encerra antes da publicação atômica.
                        publish(
                            temporary,
                            target.name,
                            directory_fd,
                            input_fd,
                            request.overwrite,
                            expected,
                        )
                    return ConversionResult(
                        True, target, tuple(diagnostics), statistics, tuple(validations)
                    )
        except PrometeuError as error:
            diagnostics.append(Diagnostic(error.code, str(error), Severity.ERROR))
            code = error.exit_code
        except OSError:
            diagnostics.append(
                Diagnostic(
                    "FILESYSTEM_ERROR",
                    "Falha de acesso ao filesystem; conversão interrompida.",
                    Severity.ERROR,
                )
            )
            code = 2
        except Exception:
            diagnostics.append(
                Diagnostic(
                    "CONVERSION_FAILED",
                    "Falha interna de conversão; saída não publicada.",
                    Severity.ERROR,
                )
            )
            code = 1
        return ConversionResult(
            False,
            diagnostics=tuple(diagnostics),
            statistics=statistics,
            validations=tuple(validations),
            exit_code=code,
        )
