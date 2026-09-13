# Prometeu Desktop — handoff

Data: 2026-09-13. Branch `feat/desktop-frontend`; baseada em
`codex/gate-e-mvp`. Consulte `git log -5` para o HEAD documental final.

## Resultado

O desktop alpha fecha o fluxo mínimo real:

```text
seletor nativo → inspeção Python → metadados editáveis → destino nativo
→ ConversionPipeline.run → EPUB validado → resultado → Mostrar no Finder
```

Metadados exportáveis: título, autor, idioma e identificador. Editora/data/capa
foram removidos da UI por não existirem no contrato de exportação. A biblioteca
continua vazia e não persistente.

## Git preservado

- `integration/mvp` permanece em `325e209` com oito diffs locais preexistentes,
  intocados. Dois arquivos coincidem com `2582b4d`; os demais representam estados
  parciais anteriores e não devem ser commitados como duplicata.
- `codex/gate-e-mvp`: `acd4f57`, publicado em `origin/codex/gate-e-mvp`.
- `feat/desktop-frontend`: commits principais `f909659` (conversão), `b1e2444`
  (CI desktop) e merge normal `f56eed3` (evidência Gate E), todos publicados.
- `origin/main` está em `997a5a3`, contém apenas LICENSE e não possui ancestral
  comum com o candidato. Não usar merge/rebase automático nem force push.
- PR desktop seguro: [#1](https://github.com/resende-g/prometeu/pull/1), base
  `codex/gate-e-mvp`.

## Implementação

- `application.desktop_convert` aceita um JSON limitado, valida tipos/caminhos e
  chama diretamente `ConversionPipeline.run` com sobrescrita desativada.
- Rust guarda entrada/saída em memória; o frontend nunca fornece caminhos ou
  executáveis. Entrada e destino vêm de diálogos nativos.
- Inspeção e conversão compartilham o runner Python, prazo externo, processo em
  grupo próprio e encerramento/reap. Nenhuma busca ou kill por nome.
- `reveal_epub` usa `/usr/bin/open -R` no macOS somente com o último caminho
  publicado e retido no Rust.
- Capabilities permitem somente os três comandos específicos. Sem filesystem,
  shell, opener ou rede genéricos expostos ao JavaScript.

## Evidência local

- Python 3.11.16: 130/130 testes; Ruff, format e mypy verdes.
- Frontend: 14/14 testes; ESLint, TypeScript e Vite build verdes.
- Rust 1.98.1: cargo fmt/check verdes; 3/3 testes com `--include-ignored`, incluindo
  inspeção e conversão por Python real e terminação seletiva de subprocessos.
- E2E nativo em macOS arm64: `Amostra ação com espaços.pdf`; metadados alterados
  para valores sintéticos; EPUB com 2 páginas, 2 capítulos, 4 parágrafos e 2.482
  bytes. Resultado exibido no React e arquivo selecionado no Finder.
- EPUB reaberto: os quatro metadados e os dois itens de TOC foram confirmados.
- Validador interno: passed. EPUBCheck 5.3.0: 0 erros e 0 warnings.

## CI

- Core histórico: 6/6 jobs verdes em
  [34642131348](https://github.com/resende-g/prometeu/actions/runs/34642131348).
- Desktop com npm, Rust 1.88 e bridges Python reais: verde em
  [34787690967](https://github.com/resende-g/prometeu/actions/runs/34787690967).
- O workflow desktop usa um único job macOS, sem matriz ou bundling.

## Limitações decisivas

1. Build release ainda recusa o motor Python: falta sidecar offline empacotado.
2. `origin/main` tem história independente; integração exige decisão explícita do
   mantenedor sobre como unir ou substituir a branch inicial.
3. Linux/Windows desktop, assinatura, instalador e avisos transitivos de
   distribuição não foram validados.
4. Fechamento normal/timeout são cobertos; SIGKILL/crash do próprio app não pode
   garantir limpeza.
5. PNG de ícone é placeholder transparente.

## Retomada

```sh
cd /Users/gabriel.resende/prometeu/.worktrees/desktop
git status --short
git log --oneline --decorate -5
git fetch origin
cd apps/desktop
export PROMETEU_PYTHON="$(cd ../.. && pwd)/.venv/bin/python"
npm run tauri -- dev
```

Próximo incremento recomendado: sidecar Python/core offline, sem biblioteca,
redesign, Windows ou novos metadados no mesmo pacote. Antes disso, decidir a
integração da história independente de `main`.
