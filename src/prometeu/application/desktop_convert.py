"""Bridge privado: converte um PDF selecionado pelo shell usando o pipeline público."""

import json
import sys
from pathlib import Path

from prometeu.application.pipeline import ConversionPipeline
from prometeu.document.contracts import ConversionRequest, InputError, Severity

MAX_REQUEST_BYTES = 32 * 1024


def read_request(payload: bytes) -> ConversionRequest:
    if len(payload) > MAX_REQUEST_BYTES:
        raise InputError("REQUEST_INVALID", "Pedido de conversão inválido.")
    try:
        request = json.loads(payload)
    except (ValueError, UnicodeError, RecursionError):
        raise InputError("REQUEST_INVALID", "Pedido de conversão inválido.") from None
    fields = {"path", "output", "title", "author", "language", "identifier"}
    if not isinstance(request, dict) or set(request) != fields:
        raise InputError("REQUEST_INVALID", "Pedido de conversão inválido.")

    def text(name: str, limit: int, optional: bool = False) -> str | None:
        value = request[name]
        if optional and value is None:
            return None
        if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
            raise InputError("REQUEST_INVALID", "Pedido de conversão inválido.")
        return value

    source = Path(text("path", 16 * 1024) or "")
    output = Path(text("output", 16 * 1024) or "")
    if (
        not source.is_absolute()
        or source.suffix.lower() != ".pdf"
        or not output.is_absolute()
        or output.suffix.lower() != ".epub"
    ):
        raise InputError("REQUEST_INVALID", "Selecione caminhos locais PDF e EPUB válidos.")
    return ConversionRequest(
        source,
        output,
        title=text("title", 512),
        author=text("author", 512, optional=True),
        language=text("language", 63),
        identifier=text("identifier", 1024, optional=True),
    )


def main() -> int:
    try:
        if sys.platform != "darwin" and not sys.platform.startswith("linux"):
            raise InputError(
                "PLATFORM_UNSUPPORTED", "A conversão desktop ainda requer macOS ou Linux."
            )
        request = read_request(sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1))
        result = ConversionPipeline().run(request)
    except InputError as error:
        print(json.dumps({"ok": False, "error": {"code": error.code, "message": str(error)}}))
        return error.exit_code
    except Exception:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "CONVERSION_FAILED",
                        "message": "Não foi possível converter este PDF.",
                    },
                }
            )
        )
        return 1
    if not result.success:
        failure = next(
            (item for item in reversed(result.diagnostics) if item.severity is Severity.ERROR),
            None,
        )
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": failure.code if failure else "CONVERSION_FAILED",
                        "message": failure.message
                        if failure
                        else "Não foi possível converter este PDF.",
                    },
                }
            )
        )
        return result.exit_code or 1
    stats = result.statistics
    print(
        json.dumps(
            {
                "ok": True,
                "conversion": {
                    "output_path": str(result.published_path),
                    "pages": stats.pages,
                    "paragraphs": stats.paragraphs,
                    "chapters": stats.chapters,
                    "output_bytes": stats.output_bytes,
                },
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
