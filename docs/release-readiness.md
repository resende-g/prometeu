# Prometeu — prontidão do v0.1 e desktop alpha

Data: 2026-09-14. Pontos são concedidos apenas quando há evidência executada.
`PARTIAL` recebe somente a fração indicada; `NOT VERIFIED` recebe zero.

## Resultado

- Core v0.1 técnico: **84/84 (100%)**.
- Desktop alpha definido: **13/13 (100%)**.
- Projeto/MVP v0.1: **100/100 (100%)**.

`main` foi promovida com sucesso pelo PR #1. O HEAD validado é `81a8817`
(`81a881759fc1cf769723ff608979d5d6e0be5bfd`), com CI `34796365136`
concluído com `success`; a integração em `main` não é mais pendência.
O escopo definido do v0.1 está completo. O desktop alpha é funcional em
desenvolvimento e depende de `PROMETEU_PYTHON`; sua distribuição com sidecar
pertence ao roadmap e não é requisito deste v0.1.

## Scorecard

| Área | Peso | Estado | Pontos | Evidência |
| --- | ---: | --- | ---: | --- |
| Core PDF → EPUB | 20 | PASS | 20 | Pipeline real, publicação atômica e teste de fogo sintético |
| Reconstrução semântica | 10 | PASS | 10 | Parágrafos, continuidade e provenance; 109 testes core |
| EPUB builder + navegação | 10 | PASS | 10 | EPUB reaberto; capítulos, H1/H2/H3, anchors e TOC |
| Limpeza/normalização | 8 | PASS | 8 | Margens/paginação, deshifenização e NFC com regressões |
| Segurança e filesystem | 8 | PASS | 8 | Limites, snapshot, symlink/alias, publicação e subprocessos testados |
| Testes core | 8 | PASS | 8 | 109/109 em Python 3.11.16, 3.12.14 e 3.13.15 |
| EPUBCheck externo | 6 | PASS | 6 | EPUBCheck 5.3.0: 0 erros e 0 warnings no core e no E2E desktop |
| Build/package | 5 | PASS | 5 | Build isolado normal com setuptools 84.0.0; wheel + sdist |
| CI | 5 | PASS | 5 | Matriz core 6/6 e job desktop macOS verdes |
| Python 3.11–3.13 | 4 | PASS | 4 | Ruff, mypy, pytest e CLI nas três versões |
| Desktop inspeção | 4 | PASS | 4 | Seletor nativo → Rust → Python real → React |
| Desktop conversão real | 7 | PASS | 7 | E2E nativo: metadados, 2 páginas, 2 capítulos, 4 parágrafos, 2.482 bytes |
| Desktop lifecycle | 2 | PASS | 2 | Runner compartilhado, grupo próprio e teste que preserva processo alheio |
| Documentação/release | 3 | PASS | 3 | Gates, handoff, PR #1 integrado em main e CI 34796365136 verde |
| **Total** | **100** |  | **100** |  |

## Evidências reproduzíveis

- `main` promovida: HEAD `81a8817`; GitHub Actions
  [34796365136](https://github.com/resende-g/prometeu/actions/runs/34796365136)
  concluído com `success`.

- Core remoto: `codex/gate-e-mvp` em `acd4f57`; GitHub Actions
  [34642131348](https://github.com/resende-g/prometeu/actions/runs/34642131348).
- Desktop remoto: `feat/desktop-frontend`; PR
  [#1](https://github.com/resende-g/prometeu/pull/1); job desktop verde em
  [34787690967](https://github.com/resende-g/prometeu/actions/runs/34787690967).
- Testes locais desktop: 130/130 Python, 14/14 frontend e 3/3 Rust com os ignorados
  incluídos; Ruff, format, mypy, lint, typecheck, builds e `git diff --check` verdes.
- E2E nativo: `.cache/desktop-e2e/prometeu-e2e-20260913.epub`, artefato sintético
  local e ignorado pelo Git. Metadados e TOC foram lidos do EPUB; validação interna
  e EPUBCheck passaram.

## Limites fora do percentual atual

OCR, IA, multicoluna complexa, notas avançadas, imagens/capa, biblioteca persistente,
Windows, atualização automática e instalador multiplataforma pertencem ao roadmap,
não ao v0.1/alpha medido. Sidecar offline, assinatura e avisos de distribuição são
o próximo gate para distribuir o desktop.
