# Prometeu Desktop (prévia de desenvolvimento)

Biblioteca vazia, inspeção local e revisão de metadados. Ainda não converte,
exporta capas nem guarda livros. Sem chamadas remotas ou telemetria em runtime.

## Preparação

A partir da raiz deste checkout, crie um ambiente Python próprio e instale o core
conforme o README principal. Não aponte para o ambiente de outro checkout:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -c constraints.txt -e '.[dev]'
cd apps/desktop
npm ci
```

Node >=22.12; versões verificadas: Node 26.7.0/npm 11.19.0. Rust estável e
[pré-requisitos nativos do Tauri](https://v2.tauri.app/start/prerequisites/)
são necessários para a janela desktop. Rust não estava instalado durante esta
implementação, portanto o shell ainda requer compilação e teste manual.

## Abrir a janela desktop (macOS/Linux, com Rust instalado)

A partir de `apps/desktop`:

```sh
export PROMETEU_PYTHON="$(cd ../.. && pwd)/.venv/bin/python"
npm run tauri -- dev
```

O caminho deve ser absoluto, para um Python com **este checkout** instalado.
É configuração do desenvolvedor, nunca um parâmetro vindo da UI. Apenas debug
aceita esse intérprete. Release recusa inspeção até o sidecar ser empacotado.
Windows não é suportado pela supervisão POSIX atual do core; não há fallback
inseguro. Não foi acrescentada uma nova restrição ao core/CLI.

## Prévia visual sem Rust

```sh
npm run dev
```

Abra a URL local mostrada pelo Vite. Selecionar PDF explica que essa ação requer
o aplicativo desktop; não há upload ou backend web alternativo. Não existem
livros/inspeções demo no fluxo de produção. Mocks ficam nos testes.

## Verificações

```sh
npm run lint
npm run typecheck
npm test
npm run build
cargo check --manifest-path src-tauri/Cargo.toml
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo test --manifest-path src-tauri/Cargo.toml -- --ignored
```

O último comando requer `PROMETEU_PYTHON` configurado e usa só sample.pdf sintético.
O primeiro cargo check deve gerar Cargo.lock; revisar e commitar esse lock antes
de distribuir. Versões Rust diretas estão fixadas; transitivas não foram resolvidas.
Teste manual pendente: selecionar/cancelar/trocar PDF no diálogo nativo, inspecionar
sample.pdf, revisar campos, conferir CSP/Channel, fechar janela durante inspeção.

A marca provisória é apenas PROMETEU. `src-tauri/icons/icon.png` é um PNG
transparente exigido pelo gerador Tauri, não uma logo; substituir pelo asset oficial
antes de distribuir. Assets de marca poderão ficar em `src/assets/`.

Continuidade: [handoff](../../docs/handoffs/frontend-desktop-handoff.md) e
[arquitetura](../../docs/frontend/architecture.md).
