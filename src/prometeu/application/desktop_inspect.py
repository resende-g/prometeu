"""Bridge privado: uma requisição JSON em stdin, uma resposta JSON em stdout."""

import json
import sys
from dataclasses import asdict
from pathlib import Path

from prometeu.application.inspection import inspect_document
from prometeu.document.contracts import InputError, PrometeuError

MAX_REQUEST_BYTES = 16 * 1024


def read_path(payload: bytes) -> Path:
    if len(payload) > MAX_REQUEST_BYTES:
        raise InputError("REQUEST_INVALID", "Pedido de inspeção inválido.")
    try:
        request = json.loads(payload)
    except (ValueError, UnicodeError, RecursionError):
        raise InputError("REQUEST_INVALID", "Pedido de inspeção inválido.") from None
    if (
        not isinstance(request, dict)
        or set(request) != {"path"}
        or not isinstance(request["path"], str)
        or not request["path"]
        or "\x00" in request["path"]
    ):
        raise InputError("REQUEST_INVALID", "Pedido de inspeção inválido.")
    path = Path(request["path"])
    if not path.is_absolute() or path.suffix.lower() != ".pdf":
        raise InputError("INPUT_INVALID", "Selecione um arquivo PDF local.")
    return path


def main() -> int:
    try:
        path = read_path(sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1))
        if sys.platform != "darwin" and not sys.platform.startswith("linux"):
            raise InputError(
                "PLATFORM_UNSUPPORTED", "A inspeção desktop ainda requer macOS ou Linux."
            )
        result = inspect_document(path)
    except PrometeuError as error:
        print(json.dumps({"ok": False, "error": {"code": error.code, "message": str(error)}}))
        return error.exit_code
    except Exception:
        # Erros inesperados não podem expor conteúdo, caminhos ou stack traces na UI.
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "INSPECTION_FAILED",
                        "message": "Não foi possível inspecionar este PDF.",
                    },
                }
            )
        )
        return 1
    print(json.dumps({"ok": True, "inspection": asdict(result)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
