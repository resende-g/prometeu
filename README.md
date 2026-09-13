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

MVP verificado com dados sintéticos em macOS e Linux, Python 3.11–3.13, EPUBCheck
5.3.0 e Kindle Previewer 4.0.0. A matriz hospedada de seis jobs também passou no
GitHub Actions. As heurísticas são conservadoras e restritas a PDF textual simples
em uma coluna. A validação interna aceita somente o perfil produzido pelo builder;
EPUBCheck e Kindle continuam sendo verificações externas distintas. Consulte
[execução](docs/execution-status.md) e [gates](docs/gates.md).

## Escopo e limites

Gates A–E concluídos: 5/5; MVP: 100% do escopo definido. OCR, notas de rodapé,
layouts multicoluna, imagens, IA e associação de notas permanecem fora do
escopo. O Kindle Previewer registrou apenas o aviso não bloqueante de capa ausente;
capas e imagens não pertencem ao MVP.

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

Alpha em `apps/desktop`: seleção e inspeção nativas, edição de título, autor,
idioma e identificador, conversão pelo pipeline real, destino seguro, resultado
explícito e localização no Finder. Não persiste biblioteca. Frontend, bridges
Python e fluxos nativos foram testados em macOS arm64. Cargo.lock está versionado;
fechar durante inspeção ou conversão encerra somente os processos do aplicativo.

A CLI continua independente de Node/React/Rust. Consulte
[instruções desktop](apps/desktop/README.md), [arquitetura](docs/frontend/architecture.md)
e [handoff](docs/handoffs/frontend-desktop-handoff.md).
