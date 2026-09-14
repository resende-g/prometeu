import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

from prometeu.application.desktop_convert import MAX_REQUEST_BYTES, read_request
from prometeu.document.contracts import InputError


def request(source: Path, output: Path) -> dict[str, str | None]:
    return {
        "path": str(source),
        "output": str(output),
        "title": "Título alterado",
        "author": "Autora fictícia",
        "language": "pt-BR",
        "identifier": "urn:prometeu:desktop-test",
    }


def test_bridge_runs_real_pipeline_and_exports_metadata(tmp_path: Path) -> None:
    source = tmp_path / "amostra ação.pdf"
    source.write_bytes(Path("tests/fixtures/sample.pdf").read_bytes())
    output = tmp_path / "resultado.epub"
    run = subprocess.run(
        [sys.executable, "-I", "-m", "prometeu.application.desktop_convert"],
        input=json.dumps(request(source, output)),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    response = json.loads(run.stdout)
    assert run.returncode == 0 and response["ok"] is True
    assert response["conversion"]["output_path"] == str(output)
    with ZipFile(output) as epub:
        package = epub.read("EPUB/package.opf").decode()
    for value in ("Título alterado", "Autora fictícia", "pt-BR", "urn:prometeu:desktop-test"):
        assert value in package


@pytest.mark.parametrize(
    "payload",
    [b"{}", b"[]", b"invalid", b'{"path":"relative.pdf"}', b"x" * (MAX_REQUEST_BYTES + 1)],
)
def test_bridge_rejects_invalid_requests(payload: bytes) -> None:
    with pytest.raises(InputError):
        read_request(payload)


def test_bridge_never_overwrites_existing_output(tmp_path: Path) -> None:
    source = tmp_path / "sample.pdf"
    source.write_bytes(Path("tests/fixtures/sample.pdf").read_bytes())
    output = tmp_path / "existente.epub"
    output.write_bytes(b"preservar")
    run = subprocess.run(
        [sys.executable, "-I", "-m", "prometeu.application.desktop_convert"],
        input=json.dumps(request(source, output)),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    response = json.loads(run.stdout)
    assert run.returncode != 0 and response["ok"] is False
    assert output.read_bytes() == b"preservar"
