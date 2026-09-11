from prometeu.cli import main
from prometeu.document.contracts import ConversionResult, Diagnostic


def test_cli_escapes_terminal_controls_without_printing_document_or_paths(monkeypatch, capsys):
    monkeypatch.setattr(
        "prometeu.cli.ConversionPipeline.run",
        lambda *_: ConversionResult(
            success=False,
            exit_code=4,
            diagnostics=(Diagnostic("PDF_ERROR", "Falha\x1b[31m\r\u202e"),),
        ),
    )
    assert main(["convert", "nome-privado.pdf"]) == 4
    output = capsys.readouterr().out
    assert "\\u001b[31m\\u000d\\u202e" in output
    assert "\x1b" not in output and "nome-privado" not in output
