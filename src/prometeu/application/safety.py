"""Fronteiras de filesystem e prazo global, sem parser PDF."""

import hashlib
import os
import signal
import stat
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import FrameType

from prometeu.document.contracts import ConversionLimits, ExtractionError, InputError


@contextmanager
def output_directory(path: Path, input_path: Path) -> Iterator[tuple[Path, int]]:
    """Fixa o diretório de publicação e rejeita o caminho da entrada antes do parser."""
    try:
        target = path.parent.resolve(strict=True) / path.name
        if target == input_path.resolve(strict=True):
            raise InputError("OUTPUT_IS_INPUT", "A saída não pode substituir a entrada.")
        fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
    except OSError as error:
        raise InputError("OUTPUT_DIRECTORY", "Diretório de saída indisponível.") from error
    try:
        yield target, fd
    finally:
        os.close(fd)


@contextmanager
def deadline(seconds: float) -> Iterator[None]:
    if threading.current_thread() is not threading.main_thread() or not hasattr(
        signal, "setitimer"
    ):
        raise InputError("EXECUTION_CONTEXT", "Use a CLI em macOS/Linux no processo principal.")

    def expired(signum: int, frame: FrameType | None) -> None:
        raise ExtractionError("TIME_LIMIT", "Tempo máximo de conversão excedido.")

    old_handler = signal.getsignal(signal.SIGALRM)
    old_timer = signal.getitimer(signal.ITIMER_REAL)
    # Do not supersede a caller's active timer (its handler may implement another invariant).
    if old_timer != (0.0, 0.0):
        raise InputError("EXECUTION_CONTEXT", "Já há um temporizador ativo neste processo.")
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


@contextmanager
def open_input(path: Path, limits: ConversionLimits) -> Iterator[int]:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    except OSError as error:
        raise InputError("INPUT_UNAVAILABLE", "Não foi possível abrir a entrada.") from error
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise InputError("INPUT_NOT_FILE", "A entrada deve ser um arquivo regular.")
        if not 0 < info.st_size <= limits.max_input_bytes:
            raise InputError("INPUT_SIZE", "Entrada vazia ou acima do limite de tamanho.")
        if os.read(fd, 5) != b"%PDF-":
            raise InputError("INPUT_NOT_PDF", "Conteúdo da entrada não reconhecido como PDF.")
        os.lseek(fd, 0, os.SEEK_SET)
        yield fd
    finally:
        os.close(fd)


def snapshot(fd: int, destination: Path, limits: ConversionLimits) -> str:
    initial = os.fstat(fd)
    digest = hashlib.sha256()
    size = 0
    with destination.open("xb") as stream:
        while chunk := os.read(fd, 1024 * 1024):
            size += len(chunk)
            if size > limits.max_input_bytes:
                raise InputError("INPUT_SIZE", "Entrada excedeu limite durante a leitura.")
            stream.write(chunk)
            digest.update(chunk)
    final = os.fstat(fd)
    if (initial.st_size, initial.st_mtime_ns, initial.st_ctime_ns) != (
        final.st_size,
        final.st_mtime_ns,
        final.st_ctime_ns,
    ):
        raise InputError("INPUT_CHANGED", "A entrada foi alterada durante a leitura.")
    return digest.hexdigest()


def check_destination(
    name: str, directory_fd: int, input_fd: int, overwrite: bool
) -> os.stat_result | None:
    try:
        existing = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    original = os.fstat(input_fd)
    if (existing.st_dev, existing.st_ino) == (original.st_dev, original.st_ino):
        raise InputError("OUTPUT_IS_INPUT", "A saída não pode substituir a entrada ou um hardlink.")
    if not stat.S_ISREG(existing.st_mode):
        raise InputError(
            "OUTPUT_NOT_FILE", "Destino existente não é arquivo regular (symlink rejeitado)."
        )
    if not overwrite:
        raise InputError(
            "OUTPUT_EXISTS", "Saída já existe; use --force para substituir somente a saída."
        )
    return existing


def publish(
    temporary: Path,
    name: str,
    directory_fd: int,
    input_fd: int,
    overwrite: bool,
    expected: os.stat_result | None = None,
) -> None:
    """Publica arquivo já validado e sincronizado; sem sobrescrita usa link atômico."""
    existing = check_destination(name, directory_fd, input_fd, overwrite)
    if _signature(existing) != _signature(expected):
        raise InputError(
            "OUTPUT_CHANGED", "Destino alterado durante a conversão; publicação cancelada."
        )
    if existing is not None and overwrite:
        # rename não segue symlinks nem escreve no inode antigo ou em seus hardlinks.
        # ponytail: POSIX não fornece CAS; --force admite último escritor externo
        # entre check e rename. Use saída distinta para coordenação sem sobrescrita.
        os.replace(temporary, name, dst_dir_fd=directory_fd)
    else:
        try:
            os.link(temporary, name, dst_dir_fd=directory_fd, follow_symlinks=False)
        except FileExistsError as error:
            raise InputError(
                "OUTPUT_EXISTS", "Destino criado por outra operação; nada foi sobrescrito."
            ) from error


def _signature(info: os.stat_result | None) -> tuple[int, ...] | None:
    if info is None:
        return None
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def remaining(started: float, limits: ConversionLimits) -> float:
    seconds = limits.timeout_seconds - (time.monotonic() - started)
    if seconds <= 0:
        raise ExtractionError("TIME_LIMIT", "Tempo máximo de conversão excedido.")
    return seconds
