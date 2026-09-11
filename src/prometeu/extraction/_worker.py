"""Entrada privada do processo isolado de extração."""

from prometeu.extraction.pdfplumber_adapter import _worker_main

if __name__ == "__main__":
    _worker_main()
