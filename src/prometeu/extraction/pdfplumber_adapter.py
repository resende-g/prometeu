"""Adapter pdfplumber isolado em processo supervisionado.

O processo principal nunca importa pdfplumber. Cada operação recebe um descritor
aberto pelo principal, portanto troca de nome/arquivo durante o parsing não muda a
entrada observada pelo worker. O protocolo em stdin/stdout é JSON UTF-8 limitado.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import selectors
import signal
import stat
import subprocess
import sys
import time
from dataclasses import asdict
from functools import cache
from pathlib import Path
from typing import Any, NoReturn

from prometeu.document.contracts import (
    ConversionLimits,
    Diagnostic,
    DocumentKind,
    ExtractionError,
    InputError,
    InspectionResult,
    Severity,
    UnsupportedDocumentError,
)
from prometeu.document.model import (
    BoundingBox,
    PDFMetadata,
    PhysicalDocument,
    PhysicalLine,
    PhysicalPage,
    PhysicalSpan,
    TextStyle,
)

_MAX_IPC_BYTES = 64 * 1024 * 1024
_POLL_SECONDS = 0.02


class PdfPlumberExtractor:
    """Extrai caracteres, posições e estilos sem expor objetos do pdfplumber."""

    def inspect(self, path: Path, limits: ConversionLimits) -> InspectionResult:
        payload = _run(path, limits, "inspect")
        try:
            diagnostics = tuple(_diagnostic(item) for item in payload.get("diagnostics", ()))
            return InspectionResult(
                kind=DocumentKind(payload["kind"]),
                page_count=int(payload["page_count"]),
                text_pages=tuple(int(value) for value in payload["text_pages"]),
                visual_only_pages=tuple(int(value) for value in payload["visual_only_pages"]),
                blank_pages=tuple(int(value) for value in payload["blank_pages"]),
                metadata=_metadata(payload["metadata"]),
                diagnostics=diagnostics + (_limits_diagnostic(),),
            )
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
            raise ExtractionError(
                "PDF_INSPECTION_PROTOCOL", "Resposta inválida do parser isolado."
            ) from None

    def extract(
        self, path: Path, inspection: InspectionResult, limits: ConversionLimits
    ) -> PhysicalDocument:
        if inspection.visual_only_pages:
            raise UnsupportedDocumentError(
                "PDF_VISUAL_ONLY_CONTENT",
                "PDF contém página com conteúdo visual sem texto extraível; OCR não é suportado.",
            )
        if inspection.kind is DocumentKind.EMPTY:
            raise UnsupportedDocumentError("PDF_EMPTY", "PDF não contém texto extraível.")
        payload = _run(path, limits, "extract", _inspection_dict(inspection))
        try:
            return PhysicalDocument(
                id=str(payload["id"]),
                pages=tuple(_page(item) for item in payload["pages"]),
                metadata=_metadata(payload["metadata"]),
            )
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
            raise ExtractionError(
                "PDF_EXTRACTION_PROTOCOL", "Resposta inválida do parser isolado."
            ) from None


def _run(
    path: Path,
    limits: ConversionLimits,
    operation: str,
    inspection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        fd = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0),
        )
    except (FileNotFoundError, NotADirectoryError):
        raise InputError("INPUT_NOT_FOUND", "Arquivo de entrada não encontrado.") from None
    except OSError:
        raise InputError("INPUT_UNREADABLE", "Arquivo de entrada não pôde ser aberto.") from None

    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise InputError("INPUT_NOT_FILE", "Entrada deve ser um arquivo regular.")
        if info.st_size > limits.max_input_bytes:
            raise InputError("INPUT_TOO_LARGE", "Arquivo excede o limite de bytes de entrada.")

        request: dict[str, Any] = {
            "operation": operation,
            "fd": fd,
            "limits": asdict(limits),
        }
        if inspection is not None:
            request["inspection"] = inspection
        return _supervise(fd, request, limits, operation)
    finally:
        os.close(fd)


def _supervise(
    fd: int, request: dict[str, Any], limits: ConversionLimits, operation: str
) -> dict[str, Any]:
    encoded = json.dumps(request, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > _MAX_IPC_BYTES:
        raise ExtractionError("PDF_IPC_LIMIT", "Dados de controle excedem o limite interno.")

    deadline = time.monotonic() + limits.timeout_seconds
    process = subprocess.Popen(
        [sys.executable, "-m", "prometeu.extraction._worker"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        pass_fds=(fd,),
        close_fds=True,
    )
    assert process.stdin is not None and process.stdout is not None
    input_fd = process.stdin.fileno()
    output_fd = process.stdout.fileno()
    os.set_blocking(input_fd, False)
    os.set_blocking(output_fd, False)
    selector = selectors.DefaultSelector()
    selector.register(input_fd, selectors.EVENT_WRITE)
    selector.register(output_fd, selectors.EVENT_READ)
    sent = 0
    output = bytearray()
    stop_reason: str | None = None

    try:
        while selector.get_map() or process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                stop_reason = "timeout"
                break
            if process.poll() is None:
                rss = _rss_bytes(process.pid)
                if rss is None and process.poll() is None:
                    stop_reason = "memory_monitor"
                    break
                if rss is not None and rss > limits.memory_bytes:
                    stop_reason = "memory"
                    break

            for key, mask in selector.select(min(_POLL_SECONDS, remaining)):
                if key.fd == input_fd and mask & selectors.EVENT_WRITE:
                    try:
                        sent += os.write(input_fd, encoded[sent:])
                    except BrokenPipeError:
                        sent = len(encoded)
                    if sent == len(encoded):
                        selector.unregister(input_fd)
                        process.stdin.close()
                elif key.fd == output_fd and mask & selectors.EVENT_READ:
                    chunk = os.read(output_fd, 65536)
                    if chunk:
                        output.extend(chunk)
                        if len(output) > _MAX_IPC_BYTES:
                            stop_reason = "ipc"
                            break
                    else:
                        selector.unregister(output_fd)
            if stop_reason is not None:
                break

        if stop_reason is not None:
            process.kill()
        return_code = process.wait()
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdin.close()
        process.stdout.close()

    prefix = "PDF_INSPECTION" if operation == "inspect" else "PDF_EXTRACTION"
    if stop_reason == "timeout":
        raise ExtractionError(f"{prefix}_TIMEOUT", "Processamento do PDF excedeu o tempo limite.")
    if stop_reason == "memory":
        raise ExtractionError(
            f"{prefix}_MEMORY_LIMIT", "Processamento do PDF excedeu a memória limite."
        )
    if stop_reason == "memory_monitor":
        raise ExtractionError(
            f"{prefix}_MEMORY_MONITOR",
            "Monitor de memória do processo isolado ficou indisponível.",
        )
    if stop_reason == "ipc":
        raise ExtractionError(f"{prefix}_IPC_LIMIT", "Resposta do parser excedeu o limite interno.")
    if return_code < 0 and -return_code == signal.SIGXCPU:
        raise ExtractionError(
            f"{prefix}_CPU_LIMIT", "Processamento do PDF excedeu o limite de CPU."
        )
    if not output:
        raise ExtractionError(f"{prefix}_FAILED", "Processamento isolado do PDF falhou.")
    try:
        response = json.loads(output)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ExtractionError(
            f"{prefix}_PROTOCOL", "Resposta inválida do parser isolado."
        ) from None
    if not isinstance(response, dict):
        raise ExtractionError(f"{prefix}_PROTOCOL", "Resposta inválida do parser isolado.")
    if response.get("ok") is not True:
        _raise_worker_error(response, prefix)
    result = response.get("result")
    if not isinstance(result, dict):
        raise ExtractionError(f"{prefix}_PROTOCOL", "Resposta inválida do parser isolado.")
    return result


def _rss_bytes(pid: int) -> int | None:
    if sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{pid}/statm", encoding="ascii") as stream:
                resident_pages = int(stream.read().split()[1])
            return resident_pages * os.sysconf("SC_PAGE_SIZE")
        except (FileNotFoundError, IndexError, OSError, ValueError):
            return None
    if sys.platform == "darwin":
        try:
            buffer = ctypes.create_string_buffer(512)
            function = _darwin_rss_function()
            if function is None:
                return None
            if function(pid, 2, ctypes.byref(buffer)) != 0:  # RUSAGE_INFO_V2
                return None
            return int.from_bytes(buffer.raw[64:72], sys.byteorder)
        except (AttributeError, OSError):
            return None
    return None


@cache
def _darwin_rss_function() -> Any | None:
    try:
        libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        function = libproc.proc_pid_rusage
        function.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
        function.restype = ctypes.c_int
        return function
    except (AttributeError, OSError):
        return None


def _limits_diagnostic() -> Diagnostic:
    if sys.platform.startswith("linux"):
        message = (
            "Limites aplicados: tempo de parede supervisionado; CPU por RLIMIT_CPU; "
            "memória virtual por RLIMIT_AS e RSS por /proc, amostrada a cada 20 ms."
        )
        code = "PDF_LIMITS_LINUX"
    elif sys.platform == "darwin":
        message = (
            "Limites aplicados: tempo de parede supervisionado; CPU por RLIMIT_CPU; "
            "RSS por libproc, amostrada a cada 20 ms; RLIMIT_AS não é usado no macOS."
        )
        code = "PDF_LIMITS_MACOS"
    else:
        message = "Limite aplicado: tempo de parede supervisionado; CPU e memória indisponíveis."
        code = "PDF_LIMITS_PARTIAL"
    return Diagnostic(code, message, Severity.INFO)


def _inspection_dict(value: InspectionResult) -> dict[str, Any]:
    return {
        "kind": value.kind.value,
        "page_count": value.page_count,
        "text_pages": list(value.text_pages),
        "visual_only_pages": list(value.visual_only_pages),
        "blank_pages": list(value.blank_pages),
        "metadata": asdict(value.metadata),
    }


def _metadata(value: dict[str, Any]) -> PDFMetadata:
    return PDFMetadata(
        title=value.get("title"),
        author=value.get("author"),
        language=value.get("language"),
    )


def _diagnostic(value: dict[str, Any]) -> Diagnostic:
    return Diagnostic(str(value["code"]), str(value["message"]), Severity(value["severity"]))


def _page(value: dict[str, Any]) -> PhysicalPage:
    return PhysicalPage(
        number=int(value["number"]),
        width=float(value["width"]),
        height=float(value["height"]),
        lines=tuple(_line(item) for item in value["lines"]),
        image_count=int(value["image_count"]),
        has_visual_content=bool(value["has_visual_content"]),
    )


def _line(value: dict[str, Any]) -> PhysicalLine:
    return PhysicalLine(
        id=str(value["id"]),
        page=int(value["page"]),
        bbox=_bbox(value["bbox"]),
        spans=tuple(_span(item) for item in value["spans"]),
    )


def _span(value: dict[str, Any]) -> PhysicalSpan:
    style = value["style"]
    return PhysicalSpan(
        id=str(value["id"]),
        text=str(value["text"]),
        bbox=_bbox(value["bbox"]),
        style=TextStyle(
            font_name=str(style["font_name"]),
            size=float(style["size"]),
            bold=bool(style["bold"]),
            italic=bool(style["italic"]),
        ),
    )


def _bbox(value: list[float]) -> BoundingBox:
    return BoundingBox(*(float(item) for item in value))


class _WorkerFailure(Exception):
    def __init__(self, category: str, code: str, message: str) -> None:
        super().__init__(message)
        self.category = category
        self.code = code


def _fail(category: str, code: str, message: str) -> NoReturn:
    raise _WorkerFailure(category, code, message)


def _worker_main() -> None:
    try:
        raw = sys.stdin.buffer.read(_MAX_IPC_BYTES + 1)
        if len(raw) > _MAX_IPC_BYTES:
            _fail("extraction", "PDF_IPC_LIMIT", "Dados de controle excedem o limite interno.")
        request = json.loads(raw)
        if not isinstance(request, dict):
            raise ValueError
        limits = request["limits"]
        _apply_resource_limits(limits)
        operation = request["operation"]
        if operation == "inspect":
            result = _worker_inspect(int(request["fd"]), limits)
        elif operation == "extract":
            result = _worker_extract(int(request["fd"]), request["inspection"], limits)
        else:
            raise ValueError
        _send({"ok": True, "result": result})
    except _WorkerFailure as error:
        _send(
            {
                "ok": False,
                "error": {
                    "category": error.category,
                    "code": error.code,
                    "message": str(error),
                },
            }
        )
    except MemoryError:
        _send(
            {
                "ok": False,
                "error": {
                    "category": "extraction",
                    "code": "PDF_MEMORY_LIMIT",
                    "message": "Processamento do PDF excedeu a memória limite.",
                },
            }
        )
    except BaseException:
        _send(
            {
                "ok": False,
                "error": {
                    "category": "extraction",
                    "code": "PDF_MALFORMED",
                    "message": "PDF inválido ou malformado.",
                },
            }
        )


def _apply_resource_limits(limits: dict[str, Any]) -> None:
    import resource

    cpu = max(1, math.ceil(float(limits["cpu_seconds"])))

    def cpu_exceeded(_signum: int, _frame: Any) -> NoReturn:
        _fail("extraction", "PDF_CPU_LIMIT", "Processamento do PDF excedeu o limite de CPU.")

    signal.signal(signal.SIGXCPU, cpu_exceeded)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
    if sys.platform.startswith("linux"):
        memory = int(limits["memory_bytes"])
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))


def _open_pdf(fd: int) -> tuple[Any, Any]:
    import pdfplumber
    from pdfminer.pdfdocument import PDFEncryptionError, PDFPasswordIncorrect
    from pdfplumber.utils.exceptions import PdfminerException

    stream = os.fdopen(os.dup(fd), "rb")
    try:
        pdf = pdfplumber.open(stream)
    except PdfminerException as error:
        stream.close()
        cause = error.args[0] if error.args else None
        if isinstance(cause, (PDFPasswordIncorrect, PDFEncryptionError)):
            _fail("unsupported", "PDF_ENCRYPTED", "PDF criptografado não é suportado.")
        _fail("extraction", "PDF_MALFORMED", "PDF inválido ou malformado.")
    except Exception:
        stream.close()
        _fail("extraction", "PDF_MALFORMED", "PDF inválido ou malformado.")
    if pdf.doc.encryption is not None:
        stream.close()
        _fail("unsupported", "PDF_ENCRYPTED", "PDF criptografado não é suportado.")
    return pdf, stream


def _iter_pages(pdf: Any, max_pages: int) -> Any:
    from pdfminer.pdfpage import PDFPage
    from pdfplumber.page import Page

    doctop = 0.0
    try:
        source = PDFPage.create_pages(pdf.doc)
        for index, page_object in enumerate(source, 1):
            if index > max_pages:
                _fail("input", "PDF_TOO_MANY_PAGES", "PDF excede o limite de páginas.")
            page = Page(pdf, page_object, page_number=index, initial_doctop=doctop)
            try:
                yield page
            finally:
                doctop += page.height
                page.close()
    except _WorkerFailure:
        raise
    except Exception:
        _fail("extraction", "PDF_MALFORMED", "PDF inválido ou malformado.")


def _worker_inspect(fd: int, limits: dict[str, Any]) -> dict[str, Any]:
    pdf, stream = _open_pdf(fd)
    text_pages: list[int] = []
    visual_only_pages: list[int] = []
    blank_pages: list[int] = []
    characters = 0
    page_count = 0
    try:
        metadata, diagnostics = _read_metadata(pdf)
        for page in _iter_pages(pdf, int(limits["max_pages"])):
            page_count = page.page_number
            _page_dimensions(page)
            chars = page.chars
            characters += sum(len(_char_text(char)) for char in chars)
            if characters > int(limits["max_characters"]):
                _fail("input", "PDF_TOO_MANY_CHARACTERS", "PDF excede o limite de caracteres.")
            has_text = any(_char_text(char).strip() for char in chars)
            has_visual = _has_visual_content(page.objects)
            if has_text:
                text_pages.append(page_count)
            elif has_visual:
                visual_only_pages.append(page_count)
            else:
                blank_pages.append(page_count)
    finally:
        pdf.flush_cache()
        stream.close()

    if text_pages and visual_only_pages:
        kind = "mixed"
    elif text_pages:
        kind = "textual"
    elif visual_only_pages:
        kind = "scanned"
    else:
        kind = "empty"
    return {
        "kind": kind,
        "page_count": page_count,
        "text_pages": text_pages,
        "visual_only_pages": visual_only_pages,
        "blank_pages": blank_pages,
        "metadata": metadata,
        "diagnostics": diagnostics,
    }


def _worker_extract(fd: int, inspection: dict[str, Any], limits: dict[str, Any]) -> dict[str, Any]:
    pdf, stream = _open_pdf(fd)
    pages: list[dict[str, Any]] = []
    characters = 0
    budget = 0
    observed_text: list[int] = []
    observed_visual_only: list[int] = []
    observed_blank: list[int] = []
    try:
        metadata, _ = _read_metadata(pdf)
        for page in _iter_pages(pdf, int(limits["max_pages"])):
            width, height = _page_dimensions(page)
            chars = page.chars
            page_chars = sum(len(_char_text(char)) for char in chars)
            characters += page_chars
            if characters > int(limits["max_characters"]):
                _fail("input", "PDF_TOO_MANY_CHARACTERS", "PDF excede o limite de caracteres.")
            has_text = any(_char_text(char).strip() for char in chars)
            has_visual = _has_visual_content(page.objects)
            if has_text:
                observed_text.append(page.page_number)
            elif has_visual:
                observed_visual_only.append(page.page_number)
            else:
                observed_blank.append(page.page_number)
            lines = _physical_lines(page.page_number, chars)
            budget += 256 + page_chars * 4 + len(lines) * 256
            budget += sum(len(line["spans"]) * 192 for line in lines)
            if budget > _MAX_IPC_BYTES // 2:
                _fail("extraction", "PDF_IPC_LIMIT", "Documento físico excede o limite interno.")
            pages.append(
                {
                    "number": page.page_number,
                    "width": width,
                    "height": height,
                    "lines": lines,
                    "image_count": len(page.objects.get("image", ())),
                    "has_visual_content": has_visual,
                }
            )
    finally:
        pdf.flush_cache()
        stream.close()

    if (
        len(pages) != int(inspection["page_count"])
        or observed_text != inspection["text_pages"]
        or observed_visual_only != inspection["visual_only_pages"]
        or observed_blank != inspection["blank_pages"]
        or metadata != inspection["metadata"]
    ):
        _fail(
            "extraction",
            "PDF_INSPECTION_MISMATCH",
            "PDF não corresponde à inspeção fornecida.",
        )
    return {
        "id": _content_id(fd, int(limits["max_input_bytes"])),
        "pages": pages,
        "metadata": metadata,
    }


def _physical_lines(page_number: int, chars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared = [_prepared_char(char) for char in chars if _char_text(char)]
    prepared.sort(key=lambda char: (char["bottom"], char["x0"]))
    groups: list[dict[str, Any]] = []
    for char in prepared:
        if groups and _same_line(groups[-1], char):
            group = groups[-1]
            group["chars"].append(char)
            count = len(group["chars"])
            group["baseline"] += (char["bottom"] - group["baseline"]) / count
            group["top"] = min(group["top"], char["top"])
            group["bottom"] = max(group["bottom"], char["bottom"])
        else:
            groups.append(
                {
                    "chars": [char],
                    "baseline": char["bottom"],
                    "top": char["top"],
                    "bottom": char["bottom"],
                }
            )

    groups.sort(key=lambda group: (group["top"], min(char["x0"] for char in group["chars"])))
    lines: list[dict[str, Any]] = []
    for line_index, group_info in enumerate(groups, 1):
        group = group_info["chars"]
        group.sort(key=lambda char: (char["x0"], char["top"]))
        line_id = f"p{page_number}-l{line_index}"
        spans: list[dict[str, Any]] = []
        for char in group:
            style = _style(char)
            if spans and spans[-1]["style"] == style:
                spans[-1]["text"] += char["text"]
                spans[-1]["bbox"] = _union(spans[-1]["bbox"], _char_bbox(char))
            else:
                spans.append(
                    {
                        "id": "",
                        "text": char["text"],
                        "bbox": _char_bbox(char),
                        "style": style,
                    }
                )
        for span_index, span in enumerate(spans, 1):
            span["id"] = f"{line_id}-s{span_index}"
        lines.append(
            {
                "id": line_id,
                "page": page_number,
                "bbox": _union_many([span["bbox"] for span in spans]),
                "spans": spans,
            }
        )
    return lines


def _prepared_char(char: dict[str, Any]) -> dict[str, Any]:
    text = _char_text(char)
    x0 = _finite(char.get("x0"))
    top = _finite(char.get("top"))
    x1 = _finite(char.get("x1"))
    bottom = _finite(char.get("bottom"))
    size = _finite(char.get("size"))
    if x1 < x0 or bottom < top or size <= 0:
        _fail("extraction", "PDF_INVALID_GEOMETRY", "PDF contém geometria textual inválida.")
    result = {
        "text": text,
        "x0": x0,
        "top": top,
        "x1": x1,
        "bottom": bottom,
        "fontname": str(char.get("fontname", "")),
        "size": size,
    }
    return result


def _char_text(char: dict[str, Any]) -> str:
    value = char.get("text", "")
    if not isinstance(value, str):
        _fail("extraction", "PDF_INVALID_TEXT", "PDF contém texto inválido.")
    return value


def _same_line(group: dict[str, Any], char: dict[str, Any]) -> bool:
    group_bottom = float(group["bottom"])
    group_top = float(group["top"])
    char_bottom = float(char["bottom"])
    char_top = float(char["top"])
    overlap = min(group_bottom, char_bottom) - max(group_top, char_top)
    smaller_height = min(
        group_bottom - group_top,
        char_bottom - char_top,
    )
    return overlap >= smaller_height * 0.5 or abs(float(group["baseline"]) - char_bottom) <= 2


def _style(char: dict[str, Any]) -> dict[str, Any]:
    name = char["fontname"]
    normalized = name.casefold()
    return {
        "font_name": name,
        "size": char["size"],
        "bold": any(marker in normalized for marker in ("bold", "black", "heavy", "semibold")),
        "italic": "italic" in normalized or "oblique" in normalized,
    }


def _char_bbox(char: dict[str, Any]) -> list[float]:
    return [char["x0"], char["top"], char["x1"], char["bottom"]]


def _union(left: list[float], right: list[float]) -> list[float]:
    return [
        min(left[0], right[0]),
        min(left[1], right[1]),
        max(left[2], right[2]),
        max(left[3], right[3]),
    ]


def _union_many(values: list[list[float]]) -> list[float]:
    result = values[0]
    for value in values[1:]:
        result = _union(result, value)
    return result


def _has_visual_content(objects: dict[str, list[dict[str, Any]]]) -> bool:
    return any(objects.get(kind) for kind in ("image", "line", "rect", "curve"))


def _page_dimensions(page: Any) -> tuple[float, float]:
    width, height = _finite(page.width), _finite(page.height)
    if width <= 0 or height <= 0:
        _fail("extraction", "PDF_INVALID_GEOMETRY", "PDF contém geometria de página inválida.")
    return width, height


def _read_metadata(pdf: Any) -> tuple[dict[str, str | None], list[dict[str, str]]]:
    from pdfminer.pdftypes import resolve1
    from pdfminer.utils import decode_text

    diagnostics: list[dict[str, str]] = []

    def value(raw: Any) -> str | None:
        raw = resolve1(raw)
        if isinstance(raw, bytes):
            raw = decode_text(raw)
        if not isinstance(raw, str) or not raw:
            return None
        if len(raw) > 16384:
            diagnostics.append(
                {
                    "code": "PDF_METADATA_TRUNCATED",
                    "message": "Metadado PDF excedeu o limite interno e foi truncado.",
                    "severity": "WARNING",
                }
            )
            return raw[:16384]
        return raw

    language = value(pdf.doc.catalog.get("Lang"))
    return (
        {
            "title": value(pdf.metadata.get("Title")),
            "author": value(pdf.metadata.get("Author")),
            "language": language,
        },
        diagnostics,
    )


def _content_id(fd: int, max_bytes: int) -> str:
    digest = hashlib.sha256()
    total = 0
    os.lseek(fd, 0, os.SEEK_SET)
    while chunk := os.read(fd, 1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            _fail("input", "INPUT_TOO_LARGE", "Arquivo excede o limite de bytes de entrada.")
        digest.update(chunk)
    return f"pdf-{digest.hexdigest()}"


def _finite(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        _fail("extraction", "PDF_INVALID_GEOMETRY", "PDF contém geometria textual inválida.")
    if not math.isfinite(result):
        _fail("extraction", "PDF_INVALID_GEOMETRY", "PDF contém geometria textual inválida.")
    return result


def _send(value: dict[str, Any]) -> None:
    encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > _MAX_IPC_BYTES:
        encoded = json.dumps(
            {
                "ok": False,
                "error": {
                    "category": "extraction",
                    "code": "PDF_IPC_LIMIT",
                    "message": "Resposta do parser excedeu o limite interno.",
                },
            },
            separators=(",", ":"),
        ).encode("utf-8")
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def _raise_worker_error(response: dict[str, Any], prefix: str) -> NoReturn:
    error = response.get("error")
    if not isinstance(error, dict):
        raise ExtractionError(f"{prefix}_PROTOCOL", "Resposta inválida do parser isolado.")
    code = str(error.get("code", f"{prefix}_FAILED"))
    if code in {"PDF_CPU_LIMIT", "PDF_MEMORY_LIMIT"}:
        code = f"{prefix}_{code.removeprefix('PDF_')}"
    message = str(error.get("message", "Processamento isolado do PDF falhou."))
    category = error.get("category")
    if category == "input":
        raise InputError(code, message)
    if category == "unsupported":
        raise UnsupportedDocumentError(code, message)
    raise ExtractionError(code, message)
