import os
import signal
import time
from pathlib import Path

import pytest

from prometeu.application.safety import (
    check_destination,
    deadline,
    open_input,
    output_directory,
    publish,
    snapshot,
)
from prometeu.document.contracts import ConversionLimits, ExtractionError, InputError


def test_snapshot_pins_open_inode_and_hashes_content(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\noriginal")
    with open_input(source, ConversionLimits()) as fd:
        source.rename(tmp_path / "original.pdf")
        source.write_bytes(b"%PDF-1.4\nreplacement")
        copied = tmp_path / "snapshot.pdf"
        digest = snapshot(fd, copied, ConversionLimits())
    import hashlib

    assert copied.read_bytes() == b"%PDF-1.4\noriginal"
    assert digest == hashlib.sha256(copied.read_bytes()).hexdigest()


@pytest.mark.parametrize("alias", ["same", "hardlink", "symlink"])
@pytest.mark.parametrize("force", [False, True])
def test_input_alias_is_rejected_even_with_force(tmp_path, alias, force):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\noriginal")
    output = source if alias == "same" else tmp_path / "alias.epub"
    if alias == "hardlink":
        output.hardlink_to(source)
    elif alias == "symlink":
        output.symlink_to(source)
    with open_input(source, ConversionLimits()) as fd:
        with pytest.raises(InputError), output_directory(output, source) as (target, directory):
            check_destination(target.name, directory, fd, force)
    assert source.read_bytes() == b"%PDF-1.4\noriginal"


@pytest.mark.parametrize("force", [False, True])
def test_destination_created_during_conversion_is_preserved(tmp_path, force):
    source, output, temporary = (tmp_path / n for n in ("source.pdf", "out.epub", "temp.epub"))
    source.write_bytes(b"%PDF-1.4")
    temporary.write_bytes(b"new")
    with (
        open_input(source, ConversionLimits()) as fd,
        output_directory(output, source) as (target, directory),
    ):
        expected = check_destination(target.name, directory, fd, force)
        output.write_bytes(b"concurrent")
        with pytest.raises(InputError):
            publish(temporary, target.name, directory, fd, force, expected)
    assert output.read_bytes() == b"concurrent"


def test_atomic_no_clobber_closes_last_check_race(tmp_path, monkeypatch):
    source, output, temporary = (tmp_path / n for n in ("source.pdf", "out.epub", "temp.epub"))
    source.write_bytes(b"%PDF-1.4")
    temporary.write_bytes(b"new")
    link = os.link

    def race(*args, **kwargs):
        output.write_bytes(b"winner")
        return link(*args, **kwargs)

    monkeypatch.setattr(os, "link", race)
    with (
        open_input(source, ConversionLimits()) as fd,
        output_directory(output, source) as (target, directory),
    ):
        with pytest.raises(InputError, match="outra operação"):
            publish(temporary, target.name, directory, fd, False)
    assert output.read_bytes() == b"winner"


def test_force_replaces_only_output_and_preserves_its_other_hardlinks(tmp_path):
    source, output, temporary = (tmp_path / n for n in ("source.pdf", "out.epub", "temp.epub"))
    source.write_bytes(b"%PDF-1.4")
    output.write_bytes(b"previous")
    alias = tmp_path / "previous.epub"
    alias.hardlink_to(output)
    temporary.write_bytes(b"validated")
    with (
        open_input(source, ConversionLimits()) as fd,
        output_directory(output, source) as (target, directory),
    ):
        expected = check_destination(target.name, directory, fd, True)
        publish(temporary, target.name, directory, fd, True, expected)
    assert output.read_bytes() == b"validated" and alias.read_bytes() == b"previous"
    assert source.read_bytes() == b"%PDF-1.4"


def test_global_deadline_is_effective_and_restores_handler():
    handler = signal.getsignal(signal.SIGALRM)
    started = time.monotonic()
    with pytest.raises(ExtractionError, match="Tempo máximo"), deadline(0.05):
        time.sleep(2)
    assert time.monotonic() - started < 1
    assert signal.getsignal(signal.SIGALRM) == handler
    assert signal.getitimer(signal.ITIMER_REAL) == (0, 0)


def test_fifo_is_rejected_without_blocking(tmp_path: Path):
    fifo = tmp_path / "fifo.pdf"
    os.mkfifo(fifo)
    with pytest.raises(InputError, match="regular"), open_input(fifo, ConversionLimits()):
        pytest.fail("FIFO aceita")


def test_snapshot_detects_in_place_mutation(tmp_path, monkeypatch):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\noriginal")
    read = os.read
    with open_input(source, ConversionLimits()) as fd:
        changed = False

        def mutate(descriptor, size):
            nonlocal changed
            data = read(descriptor, size)
            if descriptor == fd and not changed:
                changed = True
                with source.open("ab") as stream:
                    stream.write(b"changed")
            return data

        monkeypatch.setattr(os, "read", mutate)
        with pytest.raises(InputError, match="alterada durante"):
            snapshot(fd, tmp_path / "snapshot.pdf", ConversionLimits())


def test_existing_timer_is_not_replaced():
    with deadline(2):
        handler = signal.getsignal(signal.SIGALRM)
        with pytest.raises(InputError, match="temporizador ativo"), deadline(0.01):
            pytest.fail("Prazo existente foi sobrescrito")
        assert signal.getsignal(signal.SIGALRM) == handler
        assert signal.getitimer(signal.ITIMER_REAL)[0] > 1
