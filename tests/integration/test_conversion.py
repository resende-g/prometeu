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
from prometeu.document.model import Heading, PhysicalDocument, SemanticDocument
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


def test_real_pipeline_preserves_h2_h3_hierarchy_from_pdf_to_epub(tmp_path: Path) -> None:
    source = write_pdf(
        tmp_path / "hierarchy.pdf",
        (
            (
                TextLine("Capítulo", 72, 730, 22, True),
                TextLine("Abertura.", 72, 690),
                TextLine("Seção", 72, 650, 18, True),
                TextLine("Desenvolvimento.", 72, 610),
                TextLine("Subseção", 72, 570, 15, True),
                TextLine("Detalhe.", 72, 530),
            ),
        ),
        {"Title": "Hierarquia sintética"},
    )
    output = tmp_path / "hierarchy.epub"
    exporter = RecordingExporter()

    result = ConversionPipeline(exporter=exporter).run(ConversionRequest(source, output))

    assert result.success
    assert exporter.semantic is not None
    chapter = exporter.semantic.chapters[0]
    headings = ([chapter.heading] if chapter.heading else []) + [
        block for block in chapter.blocks if isinstance(block, Heading)
    ]
    assert [(heading.level, heading.text) for heading in headings] == [
        (1, "Capítulo"),
        (2, "Seção"),
        (3, "Subseção"),
    ]
    with ZipFile(output) as epub:
        content = ET.fromstring(epub.read("EPUB/chapter-0001.xhtml"))
        navigation = ET.fromstring(epub.read("EPUB/nav.xhtml"))
    body = content.find(f"{{{_XHTML}}}body")
    assert body is not None
    assert [element.tag.rsplit("}", 1)[-1] for element in body] == [
        "h1",
        "p",
        "h2",
        "p",
        "h3",
        "p",
    ]
    toc = next(
        element
        for element in navigation.iter(f"{{{_XHTML}}}nav")
        if element.get(f"{{{_EPUB}}}type") == "toc"
    )
    chapter_item = toc.find(f"{{{_XHTML}}}ol/{{{_XHTML}}}li")
    assert chapter_item is not None
    section_item = chapter_item.find(f"{{{_XHTML}}}ol/{{{_XHTML}}}li")
    assert section_item is not None
    subsection_item = section_item.find(f"{{{_XHTML}}}ol/{{{_XHTML}}}li")
    assert subsection_item is not None
    assert [
        chapter_item.findtext(f"{{{_XHTML}}}a"),
        section_item.findtext(f"{{{_XHTML}}}a"),
        subsection_item.findtext(f"{{{_XHTML}}}a"),
    ] == ["Capítulo", "Seção", "Subseção"]


def test_real_pipeline_applies_conservative_cleaning_with_provenance(tmp_path: Path) -> None:
    decomposed = "Conteu\u0301do final."
    source = write_pdf(
        tmp_path / "cleaning.pdf",
        (
            (
                TextLine("Relatório sintético", 72, 820),
                TextLine("Normalização comprovada.", 72, 740),
                TextLine("Outra normali-", 72, 700),
                TextLine("zação continua.", 72, 684),
                TextLine("Um guarda-", 72, 640),
                TextLine("chuva permanece.", 72, 624),
                TextLine("Uso fictício", 72, 40),
                TextLine("1", 280, 20),
            ),
            (
                TextLine("Relatório sintético", 72, 820),
                TextLine(decomposed, 72, 740),
                TextLine("Uso fictício", 72, 40),
                TextLine("2", 280, 20),
            ),
        ),
        {"Title": "Limpeza sintética"},
    )
    output = tmp_path / "cleaning.epub"
    extractor = RecordingExtractor()
    exporter = RecordingExporter()

    result = ConversionPipeline(extractor=extractor, exporter=exporter).run(
        ConversionRequest(source, output)
    )

    assert result.success
    assert extractor.physical is not None and exporter.semantic is not None
    physical_lines = tuple(line for page in extractor.physical.pages for line in page.lines)
    physical_texts = [line.text for line in physical_lines]
    assert decomposed in physical_texts
    assert physical_texts.count("Relatório sintético") == 2
    assert physical_texts.count("Uso fictício") == 2
    assert {"1", "2"} <= set(physical_texts)
    blocks = exporter.semantic.chapters[0].blocks
    expected = (
        "Normalização comprovada.",
        "Outra normalização continua.",
        "Um guarda- chuva permanece.",
        "Conteúdo final.",
    )
    assert tuple(block.text for block in blocks) == expected
    origins = {line.text: line.source.lines[0] for line in physical_lines}
    assert blocks[1].source.lines == (origins["Outra normali-"], origins["zação continua."])
    assert blocks[2].source.lines == (origins["Um guarda-"], origins["chuva permanece."])
    assert (
        result.statistics.physical_lines,
        result.statistics.paragraphs,
        result.statistics.removed_lines,
        result.statistics.dehyphenations,
    ) == (12, 4, 6, 1)
    with ZipFile(output) as epub:
        content = ET.fromstring(epub.read("EPUB/chapter-0001.xhtml"))
    assert (
        tuple("".join(element.itertext()) for element in content.iter(f"{{{_XHTML}}}p")) == expected
    )


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
