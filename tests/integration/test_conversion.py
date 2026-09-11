import hashlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_STORED, ZipFile

import pytest
from tests.support.pdf import TextLine, write_pdf

from prometeu.application.pipeline import ConversionPipeline
from prometeu.document.contracts import (
    ConversionLimits,
    ConversionRequest,
    Diagnostic,
    ExportError,
    ExportOptions,
    InspectionResult,
    Severity,
    ValidationResult,
    ValidationStatus,
)
from prometeu.document.model import PhysicalDocument, SemanticDocument
from prometeu.epub import EPUBBuilder
from prometeu.extraction import PdfPlumberExtractor
from prometeu.validation import InternalEPUBValidator

_SAMPLE = Path(__file__).parents[1] / "fixtures" / "sample.pdf"
_XHTML = "http://www.w3.org/1999/xhtml"
_EPUB = "http://www.idpf.org/2007/ops"
_OPF = "http://www.idpf.org/2007/opf"
_DC = "http://purl.org/dc/elements/1.1/"
_EXPECTED_LINES = (
    "Capítulo 1 — A origem",
    "A primeira ação começa aqui e",
    "continua na linha seguinte.",
    "Este é outro parágrafo, após um intervalo maior.",
    "Capítulo 2 — Continuidade",
    "Unicode extraível: café, ação e 世界.",
    "Fim da amostra sintética.",
)
_EXPECTED_PARAGRAPHS = (
    "A primeira ação começa aqui e continua na linha seguinte.",
    "Este é outro parágrafo, após um intervalo maior.",
    "Unicode extraível: café, ação e 世界.",
    "Fim da amostra sintética.",
)
_EXPECTED_HEADINGS = ("Capítulo 1 — A origem", "Capítulo 2 — Continuidade")


class RecordingExtractor:
    def __init__(self) -> None:
        self.delegate = PdfPlumberExtractor()
        self.physical: PhysicalDocument | None = None

    def inspect(self, path: Path, limits: ConversionLimits) -> InspectionResult:
        return self.delegate.inspect(path, limits)

    def extract(
        self, path: Path, inspection: InspectionResult, limits: ConversionLimits
    ) -> PhysicalDocument:
        self.physical = self.delegate.extract(path, inspection, limits)
        return self.physical


class RecordingExporter:
    def __init__(self) -> None:
        self.delegate = EPUBBuilder()
        self.semantic: SemanticDocument | None = None

    def export(self, document: SemanticDocument, path: Path, options: ExportOptions) -> None:
        self.semantic = document
        self.delegate.export(document, path, options)


class RecordingValidator:
    def __init__(self) -> None:
        self.delegate = InternalEPUBValidator()

    def validate(self, path: Path, limits: ConversionLimits) -> ValidationResult:
        return self.delegate.validate(path, limits)


class PartialExporter:
    def export(self, document: SemanticDocument, path: Path, options: ExportOptions) -> None:
        path.write_bytes(b"partial")
        raise ExportError("PARTIAL_EXPORT", "Falha sintética após escrita parcial.")


class MissingExporter:
    def export(self, document: SemanticDocument, path: Path, options: ExportOptions) -> None:
        pass


class StatusValidator:
    def __init__(self, status: ValidationStatus) -> None:
        self.status = status

    def validate(self, path: Path, limits: ConversionLimits) -> ValidationResult:
        diagnostics = (
            (Diagnostic("SYNTHETIC_VALIDATION", "Falha sintética.", Severity.ERROR),)
            if self.status is ValidationStatus.FAILED
            else ()
        )
        return ValidationResult("synthetic", self.status, diagnostics)


def _copy_sample(tmp_path: Path) -> Path:
    return Path(shutil.copyfile(_SAMPLE, tmp_path / "sample.pdf"))


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "prometeu", *arguments],
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )


def _assert_destination(path: Path, previous: bytes | None) -> None:
    if previous is None:
        assert not path.exists()
    else:
        assert path.read_bytes() == previous


def test_real_pipeline_preserves_models_statistics_and_validations(tmp_path: Path) -> None:
    source = _copy_sample(tmp_path)
    output = tmp_path / "direct.epub"
    extractor = RecordingExtractor()
    exporter = RecordingExporter()
    result = ConversionPipeline(
        extractor=extractor,
        exporter=exporter,
        validator=RecordingValidator(),
    ).run(ConversionRequest(source, output))

    assert result.success and result.published_path == output
    assert extractor.physical is not None
    assert tuple(line.text for page in extractor.physical.pages for line in page.lines) == (
        _EXPECTED_LINES
    )
    assert exporter.semantic is not None
    assert tuple(
        chapter.heading.text for chapter in exporter.semantic.chapters if chapter.heading
    ) == (_EXPECTED_HEADINGS)
    assert tuple(
        block.text for chapter in exporter.semantic.chapters for block in chapter.blocks
    ) == (_EXPECTED_PARAGRAPHS)
    assert exporter.semantic.metadata.title == "Amostra sintética"
    assert exporter.semantic.metadata.author == "Projeto Prometeu"
    assert exporter.semantic.metadata.language == "und"
    assert (
        exporter.semantic.metadata.identifier
        == f"urn:sha256:{hashlib.sha256(source.read_bytes()).hexdigest()}"
    )
    assert result.statistics.pages == 2
    assert result.statistics.physical_lines == 7
    assert result.statistics.extracted_characters == 210
    assert result.statistics.paragraphs == 4
    assert result.statistics.headings == 2
    assert result.statistics.chapters == 2
    assert result.statistics.output_bytes == output.stat().st_size
    assert [
        (validation.name.casefold(), validation.status) for validation in result.validations
    ] == [
        ("internal", ValidationStatus.PASSED),
        ("epubcheck", ValidationStatus.NOT_RUN),
    ]


def test_cli_converts_sample_to_reopenable_epub_with_coherent_package(tmp_path: Path) -> None:
    source = _copy_sample(tmp_path)
    output = source.with_suffix(".epub")

    completed = _run_cli("convert", str(source))

    assert completed.returncode == 0, completed.stdout + completed.stderr
    with ZipFile(output) as epub:
        first = epub.infolist()[0]
        assert (first.filename, first.compress_type, epub.read(first)) == (
            "mimetype",
            ZIP_STORED,
            b"application/epub+zip",
        )
        package = ET.fromstring(epub.read("EPUB/package.opf"))
        chapters = (
            ET.fromstring(epub.read("EPUB/chapter-0001.xhtml")),
            ET.fromstring(epub.read("EPUB/chapter-0002.xhtml")),
        )
        navigation = ET.fromstring(epub.read("EPUB/nav.xhtml"))

    metadata = package.find(f"{{{_OPF}}}metadata")
    assert metadata is not None
    assert metadata.findtext(f"{{{_DC}}}title") == "Amostra sintética"
    assert metadata.findtext(f"{{{_DC}}}creator") == "Projeto Prometeu"
    assert metadata.findtext(f"{{{_DC}}}language") == "und"
    assert metadata.findtext(f"{{{_DC}}}identifier") == (
        f"urn:sha256:{hashlib.sha256(source.read_bytes()).hexdigest()}"
    )
    manifest = package.find(f"{{{_OPF}}}manifest")
    assert manifest is not None
    assert {
        item.get("id"): (item.get("href"), item.get("media-type"), item.get("properties"))
        for item in manifest
    } == {
        "nav": ("nav.xhtml", "application/xhtml+xml", "nav"),
        "css": ("styles.css", "text/css", None),
        "chapter-1": ("chapter-0001.xhtml", "application/xhtml+xml", None),
        "chapter-2": ("chapter-0002.xhtml", "application/xhtml+xml", None),
    }
    spine = package.find(f"{{{_OPF}}}spine")
    assert spine is not None
    assert [item.get("idref") for item in spine] == ["chapter-1", "chapter-2"]
    first_body = chapters[0].find(f"{{{_XHTML}}}body")
    second_body = chapters[1].find(f"{{{_XHTML}}}body")
    assert first_body is not None and second_body is not None
    assert [
        [element.tag.rsplit("}", 1)[-1] for element in body] for body in (first_body, second_body)
    ] == [
        ["h1", "p", "p"],
        ["h1", "p", "p"],
    ]
    assert (
        tuple(
            "".join(element.itertext())
            for body in (first_body, second_body)
            for element in body
            if element.tag == f"{{{_XHTML}}}p"
        )
        == _EXPECTED_PARAGRAPHS
    )
    toc = next(
        element
        for element in navigation.iter(f"{{{_XHTML}}}nav")
        if element.get(f"{{{_EPUB}}}type") == "toc"
    )
    links = list(toc.iter(f"{{{_XHTML}}}a"))
    assert ["".join(link.itertext()) for link in links] == list(_EXPECTED_HEADINGS)
    assert [link.get("href", "").split("#", 1)[0] for link in links] == [
        "chapter-0001.xhtml",
        "chapter-0002.xhtml",
    ]
    assert (
        InternalEPUBValidator().validate(output, ConversionLimits()).status
        is ValidationStatus.PASSED
    )


@pytest.mark.parametrize("existing", [False, True])
def test_partial_export_never_publishes_or_replaces_destination(
    tmp_path: Path, existing: bool
) -> None:
    source = _copy_sample(tmp_path)
    input_before = source.read_bytes()
    output = tmp_path / "partial.epub"
    previous = b"previous output" if existing else None
    if previous is not None:
        output.write_bytes(previous)

    result = ConversionPipeline(exporter=PartialExporter()).run(
        ConversionRequest(source, output, overwrite=existing)
    )

    assert not result.success and result.exit_code == 5
    assert [diagnostic.code for diagnostic in result.diagnostics][-1] == "PARTIAL_EXPORT"
    assert source.read_bytes() == input_before
    _assert_destination(output, previous)


def test_exporter_that_creates_no_temporary_is_an_export_error(tmp_path: Path) -> None:
    source = _copy_sample(tmp_path)
    output = tmp_path / "missing.epub"

    result = ConversionPipeline(exporter=MissingExporter()).run(ConversionRequest(source, output))

    assert not result.success and result.exit_code == 5
    assert "EPUB_NOT_CREATED" in {diagnostic.code for diagnostic in result.diagnostics}
    assert not output.exists()


def test_slow_fsync_times_out_before_publication(tmp_path: Path, monkeypatch) -> None:
    source = _copy_sample(tmp_path)
    input_before = source.read_bytes()
    output = tmp_path / "slow.epub"
    started = time.monotonic()

    monkeypatch.setattr(os, "fsync", lambda _fd: time.sleep(5))
    result = ConversionPipeline().run(
        ConversionRequest(source, output, limits=ConversionLimits(timeout_seconds=2))
    )

    assert not result.success and result.exit_code == 4
    assert "TIME_LIMIT" in {diagnostic.code for diagnostic in result.diagnostics}
    assert time.monotonic() - started < 4
    assert source.read_bytes() == input_before
    assert not output.exists()


@pytest.mark.parametrize("status", [ValidationStatus.FAILED, ValidationStatus.NOT_RUN])
@pytest.mark.parametrize("existing", [False, True])
def test_unsuccessful_validation_never_publishes_or_replaces_destination(
    tmp_path: Path, status: ValidationStatus, existing: bool
) -> None:
    source = _copy_sample(tmp_path)
    input_before = source.read_bytes()
    output = tmp_path / "invalid.epub"
    previous = b"previous output" if existing else None
    if previous is not None:
        output.write_bytes(previous)

    result = ConversionPipeline(validator=StatusValidator(status)).run(
        ConversionRequest(source, output, overwrite=existing)
    )

    assert not result.success and result.exit_code == 6
    assert result.validations[0].status is status
    assert source.read_bytes() == input_before
    _assert_destination(output, previous)


def test_cli_force_rejects_output_hardlinked_to_input(tmp_path: Path) -> None:
    source = _copy_sample(tmp_path)
    input_before = source.read_bytes()
    output = source.with_suffix(".epub")
    os.link(source, output)

    completed = _run_cli("convert", str(source), "--force")

    assert completed.returncode == 2
    assert "OUTPUT_IS_INPUT" in completed.stdout
    assert source.read_bytes() == output.read_bytes() == input_before


def test_invalid_xml_character_is_preserved_physically_and_rejected_before_export(
    tmp_path: Path,
) -> None:
    source = write_pdf(tmp_path / "invalid-xml.pdf", ((TextLine("A\x00B", 72, 770),),))
    input_before = source.read_bytes()
    output = source.with_suffix(".epub")
    extractor = RecordingExtractor()

    result = ConversionPipeline(extractor=extractor).run(ConversionRequest(source, output))

    assert extractor.physical is not None
    assert extractor.physical.pages[0].lines[0].text == "A\x00B"
    assert not result.success and result.exit_code == 5
    assert "XML_CHARACTER" in {diagnostic.code for diagnostic in result.diagnostics}
    assert source.read_bytes() == input_before
    assert not output.exists()
