# Evidências de gates

Snapshot local de 2026-09-11: macOS arm64, CPython 3.11.16, HEAD destacado em
`325e209`. Nos comandos atuais abaixo, `python` e `prometeu` designam os executáveis
do venv local reutilizado, com `PYTHONPATH=src`; não houve instalação nem rede.
Fixtures e casos de teste são fictícios ou sintéticos.

## Gate A — bootstrap histórico, 2026-09-07

Gate A comprovou bootstrap, contratos e ferramentas: 9 testes, Ruff em 17 arquivos,
mypy em 8 arquivos, os dois helps e `python -m build` passaram. Naquela execução,
build 1.6.0 usou setuptools 84.0.0 e gerou wheel e sdist 0.1.0. Conversão ficou fora
do escopo daquele gate; o estado funcional atual é comprovado pelos Gates B–D.

## Gate B — pipeline textual, validação e publicação

**Fechado por evidência local.** O fluxo abre e copia uma entrada PDF regular,
inspeciona e extrai em subprocessos supervisionados, preserva `PhysicalDocument`,
reconstrói `SemanticDocument`, gera EPUB 3 temporário, reabre-o no validador interno,
sincroniza o arquivo e só então publica. Falha de exportação ou validação não publica
nem substitui a saída. Sem `--force`, a publicação usa criação atômica sem
sobrescrita; com `--force`, substitui somente o destino regular já verificado.

Comando focal atual:

```sh
python -m pytest \
  tests/integration/test_conversion.py::test_real_pipeline_preserves_models_statistics_and_validations \
  tests/integration/test_conversion.py::test_cli_converts_sample_to_reopenable_epub_with_coherent_package \
  tests/integration/test_conversion.py::test_partial_export_never_publishes_or_replaces_destination \
  tests/integration/test_conversion.py::test_unsuccessful_validation_never_publishes_or_replaces_destination \
  tests/unit/test_safety.py::test_atomic_no_clobber_closes_last_check_race \
  tests/unit/test_safety.py::test_force_replaces_only_output_and_preserves_its_other_hardlinks
```

Resultado: 10 testes passaram. Limites comprovados: PDF escaneado/misto não é
convertido; o validador cobre apenas o perfil interno; `--force` não oferece CAS
contra alteração externa posterior à última verificação; execução atual só em
macOS/Python 3.11.

## Gate C — estrutura e navegação

**Fechado por evidência local.** Continuidade entre páginas só é unida quando
posição, estilo, pontuação e caixa corroboram a decisão. Linhas únicas, negritas e
maiores que o corpo são classificadas por até três níveis tipográficos: H1 inicia
capítulo; H2/H3 permanecem em ordem nos blocos. XHTML e TOC preservam H1/H2/H3,
hierarquia e anchors.

Comando focal atual:

```sh
python -m pytest \
  tests/unit/test_reconstruction_metadata.py::test_typographic_tiers_reconstruct_h1_h2_h3_in_order_with_provenance \
  tests/unit/test_epub_builder.py::test_xhtml_and_toc_preserve_heading_hierarchy_and_anchor_targets \
  tests/integration/test_conversion.py::test_real_pipeline_preserves_h2_h3_hierarchy_from_pdf_to_epub
```

Resultado: 3 testes passaram. Limites comprovados: títulos em várias linhas e
negrito do tamanho do corpo não viram heading; continuidade incerta permanece
separada; a heurística não cobre layouts multicoluna.

## Gate D — limpeza conservadora e Unicode

**Fechado por evidência local.** Texto recorrente é removido apenas quando reaparece
na mesma margem em mais de uma página. Números decimais isolados são paginação apenas
nas margens; formas decoradas (`- 17 -`, `[17]`, `Página 17`) exigem sequência com o
mesmo deslocamento em mais de uma página. A deshifenização remove somente `-` ASCII
em quebra física adjacente, com continuação minúscula, palavra unida corroborada no
documento e forma hifenizada ausente. NFC é aplicado por `Inline` semântico; texto
físico, IDs, `SourceReference`, estilos, headings e ordem são preservados.

Comando focal atual:

```sh
python -m pytest \
  tests/unit/test_reconstruction_metadata.py::test_nfc_normalizes_only_semantic_run_text \
  tests/unit/test_reconstruction_metadata.py::test_dehyphenation_requires_a_corroborated_physical_line_break \
  tests/unit/test_reconstruction_metadata.py::test_normalization_removes_only_sequenced_decorated_pagination \
  tests/integration/test_conversion.py::test_real_pipeline_applies_conservative_cleaning_with_provenance
```

Resultado: 4 testes passaram. Na regressão ponta a ponta, 12 linhas físicas geram
4 parágrafos, 6 linhas são removidas e ocorre 1 deshifenização. O PDF e o modelo
físico conservam `Conteu\u0301do`; modelo semântico e XHTML contêm `Conteúdo`.
Hífens Unicode, soft hyphen e casos sem corroboração permanecem.

## Verificação conjunta — 2026-09-11

| Comando | Saída | Evidência atual |
| --- | ---: | --- |
| `python -m pytest` | 0 | 104 passed |
| `python -m ruff check .` | 0 | All checks passed; Ruff 0.16.6 |
| `python -m ruff format --check .` | 0 | 44 files already formatted |
| `python -m mypy src/prometeu` | 0 | 21 arquivos, sem erros; mypy 2.3.1 |
| `prometeu --help` | 0 | Ajuda geral |
| `prometeu convert --help` | 0 | Entrada, saída, metadados e sobrescrita |
| `git diff --check` | 0 | Nenhum erro de whitespace |

## Build local

Fato histórico: `python -m build` passou no Gate A com setuptools 84.0.0. Nesta
retomada, o venv disponível contém setuptools 79.0.1, abaixo do pin 84.0.0 de
`pyproject.toml`. Sem rede e sem alterar o ambiente externo:

| Comando | Saída | Resultado |
| --- | ---: | --- |
| `python -m build --no-isolation` | 1 | Requer setuptools 84.0.0; encontrado 79.0.1 |
| `python -m build --no-isolation --skip-dependency-check` | 0 | wheel e sdist 0.1.0 gerados localmente |

O segundo comando verifica o empacotamento com o backend disponível; não comprova
o build exato com setuptools 84.0.0.

## Gate E e escopo não comprovado

Permanecem não verificados: EPUBCheck, Kindle, Linux, Python 3.12/3.13, workflow
remoto e revisão independente. OCR, notas de rodapé, layouts multicoluna, imagens,
IA, GUI e associação de notas permanecem fora do escopo.
