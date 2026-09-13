# Evidências de gates

Verificação final de 2026-09-11. Código revisado e executado no commit
`2582b4de371de859d7ac41b106d7eb480304ea2d`, branch `codex/gate-e-mvp`.
Fixtures, EPUB e casos de teste são fictícios ou sintéticos.

## Resultado

**Gates A–E: 5/5. MVP: 100% do escopo definido.**

| Gate | Estado | Evidência principal |
| --- | --- | --- |
| A | Concluído | Bootstrap, contratos, ferramentas e build fixado |
| B | Concluído | Pipeline textual, validação interna e publicação atômica |
| C | Concluído | Continuidade conservadora, H1/H2/H3, capítulos e TOC |
| D | Concluído | Limpeza conservadora, deshifenização e NFC semântico |
| E | Concluído | Revisão, matriz local/remota, Linux, EPUBCheck e Kindle |

## Gates A–D

O Gate A comprovou o bootstrap com build 1.6.0 e setuptools 84.0.0. O Gate B
comprovou inspeção e extração supervisionadas, preservação dos modelos físico e
semântico, validação antes da publicação, `fsync`, não sobrescrita atômica e
substituição controlada com `--force`. Falhas antes da publicação preservam o
destino.

O Gate C comprovou continuidade entre páginas somente quando posição, estilo,
pontuação e caixa corroboram a decisão. Linhas únicas, negritas e maiores que o
corpo geram até três níveis: H1 inicia capítulo; H2/H3 permanecem em ordem; XHTML,
anchors e TOC preservam a hierarquia.

O Gate D comprovou remoção de texto recorrente somente na mesma margem e paginação
decimal ou decorada somente quando há sequência consistente. Números simples no
topo com evidência tipográfica de H1 são preservados; números em tamanho de corpo
continuam sendo paginação. Deshifenização exige `-` ASCII, quebra física adjacente,
continuação minúscula e palavra corroborada. NFC altera somente `Inline.text`; IDs,
`SourceReference`, estilos, headings, ordem e `PhysicalDocument` permanecem.

A regressão ponta a ponta dos Gates B–D mantém o grão explícito: 12 linhas físicas
geram 4 parágrafos; 6 linhas são removidas e ocorre 1 deshifenização. O PDF e o
modelo físico conservam `Conteu\u0301do`; modelo semântico e XHTML contêm
`Conteúdo`.

## Gate E — revisão independente

Um único revisor read-only analisou o diff completo, sem editar arquivos. Seis
achados bloqueantes foram reproduzidos e corrigidos no ponto compartilhado:

- título decimal legítimo confundido com paginação;
- paginação decorada bold confundida com heading;
- cabeçalho recorrente unido ao corpo entre páginas;
- capítulos numéricos sequenciais removidos;
- título homônimo a rodapé recorrente suprimido;
- paginação decimal bold em tamanho de corpo preservada indevidamente.

Na rodada final, sete contraprovas passaram: H1 numérico 22 pt, paginação bold
12 pt, título homônimo ao rodapé, cabeçalho cruzando página, paginação decorada
bold e os dois lados do limiar de 130%. Imports não formaram ciclo,
`git diff --check` passou e o revisor declarou zero bloqueantes.

## Matriz local macOS

Ambiente: macOS 26.6.2 build 25G83, arm64. Intérpretes isolados:

| Python | Executável | Testes | Exit code |
| --- | --- | ---: | ---: |
| 3.11.16 | `/Users/gabriel.resende/prometeu/.venv/bin/python` com `PYTHONPATH=src` | 109/109 | 0 |
| 3.12.14 | `.venv-gate-e-312/bin/python` | 109/109 | 0 |
| 3.13.15 | `.venv-gate-e-313/bin/python` | 109/109 | 0 |

O seguinte conjunto foi executado com cada intérprete; todos os comandos saíram
com código 0:

```sh
python -m ruff check .
python -m ruff format --check .
python -m mypy src/prometeu
python -m pytest -q
python -m prometeu --help
python -m prometeu convert --help
```

Resultados comuns: Ruff 0.16.6 sem achados, 44 arquivos formatados, mypy 2.3.1
sem erros em 21 arquivos e pytest 9.1.1 com 109/109 testes. `git diff --check`
também saiu com código 0.

## Build fixado, wheel e sdist

Ambientes Python 3.12.14 e 3.13.15 continham build 1.6.0 e setuptools exatamente
84.0.0. Em ambos, `python -m build --no-isolation --outdir <diretório>` saiu com
código 0 sem `--skip-dependency-check`. O workflow remoto também executou
`python -m build` isolado nos seis jobs e respeitou o pin de `pyproject.toml`.

Artefatos finais inspecionados:

| Artefato | Conteúdo | SHA-256 |
| --- | ---: | --- |
| `.cache/gate-e-final-py313/prometeu-0.1.0-py3-none-any.whl` | 27 entradas | `7c30619dc56c32f00d2ac963783ea7f7f907b01f247db2547d850e653b3639e1` |
| `.cache/gate-e-final-py313/prometeu-0.1.0.tar.gz` | 44 entradas | `6224fa530e2b6b79796014c962cd1274886f4e22dad3d5289f97b02301cd9ac6` |

O metadado `WHEEL` registra `Generator: setuptools (84.0.0)`,
`Root-Is-Purelib: true` e `Tag: py3-none-any`. O sdist contém licença, README,
`pyproject.toml` e os módulos. Em `.venv-gate-e-wheel-final`, Python 3.13.15,
foram instaladas por hash as 8 dependências de runtime e depois o wheel com
`pip install --no-deps`; import e ambos os helps partiram de `site-packages` e
saíram com código 0.

## Linux

Container real Linux: Alpine 3.23.5, aarch64, kernel LinuxKit 7.0.12 e Python
3.12.13. O comando usou `--network none --memory 2g --cpus 2 --pids-limit 256
--read-only`, com `/tmp` em tmpfs. Cgroup confirmou `memory.max=2147483648`,
`cpu.max="200000 100000"` e `pids.max=256`.

Dentro do container, Ruff, format check, mypy, 109/109 testes, build com
setuptools 84.0.0 e os dois CLI helps saíram com código 0. O repositório foi
montado somente para leitura; build e execução ocorreram em cópia temporária.

## EPUBCheck

EPUBCheck oficial 5.3.0, distribuído pelo W3C, SHA-256 do ZIP
`6c07e68584b2e2ce2f89fe06e1246dfead3eb36b46b340e7d93524f29dcff6c5`,
executado com Java 1.8.0_503 arm64:

```sh
java -jar .cache/epubcheck/epubcheck-5.3.0/epubcheck.jar \
  .cache/gate-e-external/prometeu-gate-e.epub
```

Exit code 0 usando regras EPUB 3.3: 0/0 erros fatais, 0/0 erros, 0/0 warnings e
0 informações. O EPUB sintético final tem 3 páginas físicas, 15 linhas, 2
capítulos, H1/H2/H3, Unicode, negrito/itálico, 6 linhas removidas, 1
deshifenização, validação interna aprovada e 2.475 bytes. SHA-256:
`cdef4d6f58665b70f6c51f509774739485287d2c0de50a66c6d079ad738186ac`.

## Kindle

Kindle Previewer 4.0.0 build 1, assinado por AMZN Mobile LLC:

```sh
KindlePreviewer4CLI .cache/gate-e-external/prometeu-gate-e.epub \
  --convert --qualitychecks --output .cache/gate-e-kindle --locale pt
```

Exit code 0; conversão `Success`, Enhanced Typesetting `Supported`, 0 erros e
0 problemas de qualidade. O warning não bloqueante W14016 informa capa não
especificada; capas e imagens estão fora do MVP. Na interface gráfica foram
verificados abertura, ordem, `Capítulo Um`, `Seção`, `Subseção`, `Capítulo Dois`,
TOC aninhado H1/H2/H3, `café`, `世界`, negrito, itálico e conteúdo após limpeza.

## Workflow remoto

Workflow `checks`, evento `push`, executado sobre exatamente o commit revisado:

- execução: [GitHub Actions 34642131348](https://github.com/resende-g/prometeu/actions/runs/34642131348);
- SHA: `2582b4de371de859d7ac41b106d7eb480304ea2d`;
- período: 2026-09-11 20:03:14–20:04:05 UTC;
- resultado: `success`, 6/6 jobs;
- matriz: Ubuntu e macOS, cada um com Python 3.11, 3.12 e 3.13;
- em cada job: instalação por hashes, editable sem dependências, Ruff lint,
  format check, mypy, pytest, build e dois CLI helps; todos os passos obrigatórios
  saíram com código 0.

## Limites preservados

OCR, notas de rodapé, layouts multicoluna, imagens, IA, GUI e associação de notas
não fazem parte do MVP. O adapter não é sandbox; a validação interna cobre apenas
o perfil gerado; EPUBCheck e Kindle são evidência de compatibilidade do artefato
sintético, não de PDFs arbitrários. `--force` não oferece comparação e troca
atômica contra mutação externa posterior à última verificação.
