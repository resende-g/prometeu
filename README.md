# Prometeu

Conversor local de PDF textual para EPUB 3 reflowable. Código original Apache-2.0.
Não há conta, serviço remoto, telemetria ou download durante conversão.

## Implemented

Conversão de PDF textual simples, em uma coluna, pelos modelos físico e semântico.
Inspeção e extração em subprocessos supervisionados; parágrafos reflowable,
continuidade conservadora entre páginas, headings H1/H2/H3, capítulos e TOC
hierárquico. A limpeza remove margens recorrentes e paginação simples ou decorada
sequenciada, desfaz hifenização ASCII corroborada e aplica NFC somente ao texto dos
runs semânticos. O EPUB 3 passa por validação interna antes da publicação atômica.

```sh
prometeu convert tests/fixtures/sample.pdf
prometeu convert entrada.pdf -o saida.epub --title "Título" --language pt-BR
```

Saída existente é recusada por padrão. `--force` permite substituí-la depois da
validação; entrada, seus hardlinks e destinos symlink são rejeitados. Em diretórios
com escritores concorrentes, prefira saída distinta: `--force` não oferece
comparação e troca atômica contra mudanças após a última verificação.

## Experimental

Pipeline verificado localmente em macOS/Python 3.11 com dados sintéticos. As
heurísticas são conservadoras e restritas a PDF textual simples em uma coluna.
A validação aceita o perfil produzido pelo builder; não substitui EPUBCheck nem
prova compatibilidade Kindle. Consulte [execução](docs/execution-status.md) e
[gates](docs/gates.md).

## Próxima revisão e limites

O Gate E ainda requer revisão independente. EPUBCheck, Kindle, Linux, Python
3.12/3.13 e workflow remoto permanecem não verificados. OCR, notas de rodapé,
layouts multicoluna, imagens, IA e associação de notas estão fora do escopo.

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

## Desktop — prévia em desenvolvimento

Primeira interface adicional em `apps/desktop`: biblioteca vazia, seleção nativa
e inspeção de PDF pelo core, metadados editáveis. Ainda não converte pela GUI
nem persiste a biblioteca. Frontend, bridge Python e fluxo nativo de inspeção testados em macOS arm64.
Cargo.lock versionado; fechar durante inspeção encerra Python e worker.

A CLI continua independente de Node/React/Rust. Consulte
[instruções desktop](apps/desktop/README.md), [arquitetura](docs/frontend/architecture.md)
e [handoff](docs/handoffs/frontend-desktop-handoff.md).
