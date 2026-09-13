# Prometeu Desktop alpha

Seleciona e inspeciona PDF textual, revisa os quatro metadados exportáveis, converte
pelo core real, mostra o resultado e o localiza no Finder. Ainda não exporta capas,
persiste biblioteca nem inclui o Python em builds de distribuição. Sem chamadas
remotas ou telemetria em runtime.

## Preparação

A partir da raiz deste checkout, crie um ambiente Python próprio e instale o core
conforme o README principal. Não aponte para o ambiente de outro checkout:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -c constraints.txt -e '.[dev]'
cd apps/desktop
npm ci
```

Node >=22.12; versões verificadas: Node 26.7.0/npm 11.19.0. Rust estável (mínimo declarado 1.88; testado 1.98.1) e
[pré-requisitos nativos do Tauri](https://v2.tauri.app/start/prerequisites/)
são necessários para a janela desktop. Na segunda execução, compilação e inspeção nativa foram validadas em macOS arm64.
Se cargo não estiver no PATH, execute `. "$HOME/.cargo/env"` no terminal; a
instalação local de rustup não alterou seu perfil de shell.

## Abrir a janela desktop (macOS/Linux, com Rust instalado)

A partir de `apps/desktop`:

```sh
export PROMETEU_PYTHON="$(cd ../.. && pwd)/.venv/bin/python"
npm run tauri -- dev
```

O caminho deve ser absoluto, para um Python com **este checkout** instalado.
É configuração do desenvolvedor, nunca um parâmetro vindo da UI. Apenas debug
aceita esse intérprete. Release recusa inspeção e conversão até o sidecar ser empacotado.
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
cargo check --locked --manifest-path src-tauri/Cargo.toml
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo test --locked --manifest-path src-tauri/Cargo.toml -- --include-ignored
```

O último comando requer `PROMETEU_PYTHON` configurado e usa só sample.pdf sintético.
Cargo.lock está versionado. Os testes Rust exercitam inspeção e conversão Python
reais, além de verificar que o worker termina sem afetar um processo fora do grupo.
Validação nativa concluída: sample.pdf, cancelar/trocar/selecionar novamente, edição,
caminhos Unicode/espaços, erro controlado, EMPTY, Channel e CSP. Janela 800×600
verificada também em binário debug com assets locais, sem servidor Vite.
Fechar durante inspeção encerra o grupo Python/worker antes de sair. A verificação
manual observou os três processos ativos e seu término após fechar a janela.

Conversão nativa verificada em 2026-09-13: fixture com Unicode/espaços, título,
autor, idioma e identificador alterados, EPUB de 2.482 bytes, 2 capítulos e 4
parágrafos. O validador interno e o EPUBCheck 5.3.0 passaram sem erros ou warnings;
o botão “Mostrar no Finder” selecionou o arquivo publicado. Saída existente é
recusada, sem opção de sobrescrita na GUI.

A marca provisória é apenas PROMETEU. `src-tauri/icons/icon.png` é um PNG
transparente exigido pelo gerador Tauri, não uma logo; substituir pelo asset oficial
antes de distribuir. Assets de marca poderão ficar em `src/assets/`.

Continuidade: [handoff](../../docs/handoffs/frontend-desktop-handoff.md) e
[arquitetura](../../docs/frontend/architecture.md).
