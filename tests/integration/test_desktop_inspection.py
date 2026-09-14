import json
import subprocess
import sys
from pathlib import Path

import pytest
from tests.support.pdf import TextLine, write_pdf

from prometeu.application.desktop_inspect import MAX_REQUEST_BYTES, read_path
from prometeu.application.inspection import inspect_document
from prometeu.document.contracts import ConversionLimits, DocumentKind, InputError
from prometeu.extraction import PdfPlumberExtractor


def test_inspection_reuses_core_without_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object) -> None:
        raise AssertionError("Inspeção não pode extrair o documento inteiro")

    monkeypatch.setattr(PdfPlumberExtractor, "extract", forbidden)
    path = write_pdf(
        tmp_path / "sintético.pdf",
        [[TextLine("Texto", 72, 700)]],
        {"Title": "Livro sintético", "Author": "Autor fictício"},
    )
    result = inspect_document(path)
    assert (result.kind, result.page_count) == (DocumentKind.TEXTUAL, 1)
    assert result.metadata.title == "Livro sintético"
    assert result.metadata.author == "Autor fictício"
    assert result.metadata.language == "und"
    assert result.file_name == "sintético.pdf"
    assert not path.with_suffix(".epub").exists()
    with pytest.raises(InputError, match="limite de bytes"):
        inspect_document(path, ConversionLimits(max_input_bytes=1))


def test_empty_and_invalid_metadata_use_existing_rules(tmp_path: Path) -> None:
    path = write_pdf(tmp_path / "vazio.pdf", [[]], {"Title": "a" * 513})
    result = inspect_document(path)
    assert result.kind is DocumentKind.EMPTY
    assert result.metadata.title == "Documento sem título"
    assert any("ignorado" in warning for warning in result.warnings)


@pytest.mark.parametrize(
    "payload",
    [
        b"{}",
        b"[]",
        b"null",
        b"invalid",
        b'{"path":4}',
        b'{"path":"x.pdf"}',
        b'{"path":"/x.pdf","command":"rm"}',
        b'{"path":"/x.txt"}',
        b'{"path":"/x\\u0000.pdf"}',
        b"[" * 2000,
        b"x" * (MAX_REQUEST_BYTES + 1),
    ],
)
def test_bridge_rejects_invalid_requests(payload: bytes) -> None:
    with pytest.raises(InputError):
        read_path(payload)


def test_bridge_real_subprocess_unicode_path_and_safe_errors(tmp_path: Path) -> None:
    # Caracteres de shell e espaços são dados; nunca comandos.
    path = write_pdf(tmp_path / "livro ' $(false) ação.pdf", [[TextLine("Texto", 72, 700)]])
    for selected, expected_ok in ((path, True), (tmp_path / "inexistente.pdf", False)):
        run = subprocess.run(
            [sys.executable, "-I", "-m", "prometeu.application.desktop_inspect"],
            input=json.dumps({"path": str(selected)}),
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        response = json.loads(run.stdout)
        assert response["ok"] is expected_ok
        assert (run.returncode == 0) is expected_ok
        assert run.stderr == ""
        assert str(tmp_path) not in run.stdout
        if expected_ok:
            assert response["inspection"]["kind"] == "textual"
        else:
            assert response["error"]["code"] == "INPUT_NOT_FOUND"
