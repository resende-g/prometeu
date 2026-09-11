# Prometeu — estado de execução local

Data: 2026-09-11. HEAD `325e209`, destacado. Gates B–D fechados por evidência local;
Gate E aguarda revisão independente. Nenhum commit foi criado nesta retomada.
Comandos, contagens e limites estão em [gates.md](gates.md).

## Estado comprovado

| Gate | Estado | Evidência principal |
| --- | --- | --- |
| A | Histórico concluído | Bootstrap: 9 testes e build com setuptools 84.0.0 em 2026-09-07 |
| B | Fechado localmente | Pipeline textual, validação interna e publicação atômica; foco 10 passed |
| C | Fechado localmente | Continuidade conservadora, H1/H2/H3, capítulos e TOC; foco 3 passed |
| D | Fechado localmente | Margens, paginação, deshifenização ASCII, NFC semântico e E2E; foco 4 passed |
| E | Pendente | Revisão independente e verificações externas/multiplataforma |

A verificação conjunta atual passou com 104 testes, Ruff lint e format check, mypy
em 21 arquivos, os dois helps da CLI e `git diff --check`.

## Evidência funcional dos Gates B–D

- Gate B: PDF textual simples percorre inspeção e extração supervisionadas, modelos
  físico e semântico, builder EPUB, validação interna, fsync e publicação. Falhas
  antes da publicação preservam o destino.
- Gate C: continuidade incerta não é unida; H1 inicia capítulo, H2/H3 permanecem em
  ordem e o TOC reproduz a hierarquia com anchors válidos.
- Gate D: margens recorrentes, paginação decimal marginal e paginação decorada
  sequenciada são removidas conservadoramente. Deshifenização exige `-` ASCII e
  corroboração no texto físico. NFC altera somente o texto dos runs semânticos;
  `PhysicalDocument` permanece como evidência original.

A regressão sintética ponta a ponta comprova 12 linhas físicas → 4 parágrafos,
6 linhas removidas e 1 deshifenização. `Conteu\u0301do` permanece no PDF/modelo
físico; `Conteúdo` aparece no modelo semântico e no XHTML.

## Limitação de build

O build normal passou em execução anterior com setuptools 84.0.0. Nesta retomada,
o venv reutilizado contém setuptools 79.0.1, enquanto `pyproject.toml` exige
84.0.0. `python -m build --no-isolation` falha por essa divergência; sem rede e sem
alterar o ambiente externo, wheel e sdist foram gerados com
`python -m build --no-isolation --skip-dependency-check`. Esse resultado comprova
o empacotamento local disponível, não o backend fixado.

## Não verificado e fora de escopo

Não verificados: EPUBCheck, Kindle, Linux, Python 3.12/3.13, workflow remoto e
revisão independente. Fora de escopo: OCR, notas de rodapé, layouts multicoluna,
imagens, IA, GUI e associação de notas.

## Próxima etapa

Gate E: revisão independente do diff e das evidências, sem ampliar o escopo dos
Gates B–D.
