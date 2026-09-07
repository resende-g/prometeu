# Evidências de gates

## Gate A — 2026-09-07

macOS 26.6.2 arm64, CPython 3.11.16, pip 24.0. Ambiente isolado `.venv`.

| Comando (prefixo `.venv/bin/`) | Saída | Resultado |
| --- | --- | --- |
| `python -m pip install -c constraints.txt -e '.[dev]'` | 0 | Editável e 22 dependências runtime/dev instalados |
| `python -m ruff check .` | 0 | All checks passed; Ruff 0.16.6 |
| `python -m ruff format --check .` | 0 | 17 arquivos formatados |
| `python -m mypy src/prometeu` | 0 | 8 arquivos, sem erros; mypy 2.3.1 |
| `python -m pytest` | 0 | 9 passed, pytest 9.1.1 |
| `python -m build` | 0 | wheel e sdist 0.1.0; build 1.6.0, setuptools 84.0.0 |
| `prometeu --help` | 0 | Ajuda geral |
| `prometeu convert --help` | 0 | Entrada, saída, metadados e sobrescrita |

Antes dos checks, Ruff corrigiu ordenação de import e formatou 4 arquivos; os
checks finais acima não fizeram alterações. A conversão é stub com falha explícita.
Gate A não comprova conversão nem segurança de parser ainda inexistente.

Python 3.12.14 e 3.13.15 instalados localmente, testes ainda não executados neles.
EPUBCheck não executado (Java indisponível). Workflow configurado; execução remota
não verificada. Compatibilidade Kindle não verificada manualmente.
