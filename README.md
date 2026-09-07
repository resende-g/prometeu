# Prometeu

Conversor local de PDF textual para EPUB 3 reflowable. Código original Apache-2.0.
Não há conta, serviço remoto, telemetria ou download durante conversão.

## Implemented

Bootstrap, CLI de ajuda, modelos físicos/semânticos imutáveis e contratos mínimos.
A conversão ainda retorna erro explícito; o MVP não está concluído.

## Experimental

Nenhuma conversão utilizável nesta etapa. Consulte [execução](docs/execution-status.md).

## Planned

Inspeção e extração supervisionadas, reconstrução textual conservadora, limpeza,
EPUB próprio, validação interna e publicação atômica. OCR, IA, GUI, associação
de notas e exportação de imagens estão fora desta execução.

## Desenvolvimento

Python 3.11+. No ambiente inicial, intérpretes locais ficam em `.python/`.

```sh
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -c constraints.txt -e '.[dev]'
python -m ruff check .
python -m ruff format --check .
python -m mypy src/prometeu
python -m pytest
python -m build
prometeu --help
prometeu convert --help
```

Consulte [contratos](docs/architecture.md), [dependências](docs/dependencies.md),
[segurança](SECURITY.md) e [contribuição](CONTRIBUTING.md).
Os documentos PDF preexistentes não são fixtures autorizadas para redistribuição.
