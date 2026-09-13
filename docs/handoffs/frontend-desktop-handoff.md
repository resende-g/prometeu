# Prometeu Desktop — Handoff atualizado

## Segunda execução — fechamento prioritário
Data: 2026-09-13. Branch: `feat/desktop-frontend`.
Worktree: `.worktrees/desktop` do repositório principal.
HEAD inicial: `c25618e`. Último commit antes deste fechamento: `d0970cb`.
O usuário pediu fechamento imediato por restarem 5% de uso. Nenhum recurso novo
será iniciado. Consultar `git log -3` para o commit que contém este fechamento.

## Resultado decisivo
Gate de inspeção nativa validado em macOS arm64:
Tauri → seletor nativo → Python real → JSON/Channel → React.
`sample.pdf` sintético apresentou nome, 2 páginas, tipo textual, título
“Amostra sintética” e autor da fixture. Metadados puderam ser editados.
Conversão GUI NÃO foi iniciada: esta execução foi dedicada a fechar a inspeção.

## Preservação do checkout principal
Não alterar a worktree principal `integration/mvp`, HEAD `325e209`, com oito diffs
preexistentes: README.md, SECURITY.md, docs/execution-status.md,
src/prometeu/cleaning/normalize.py, src/prometeu/structure/reconstruct.py,
tests/integration/test_conversion.py, tests/unit/test_epub_builder.py,
tests/unit/test_reconstruction_metadata.py.
Todo trabalho desktop ocorreu na worktree isolada, baseada em `2582b4d`.
Sem reset, clean, stash, restore, merge ou push. Core maduro não alterado.

## Toolchain e dependências
- Rust 1.98.1, cargo 1.98.1, rustup 1.29.1, aarch64-apple-darwin.
- Instalação oficial via https://sh.rustup.rs, perfil minimal + rustfmt,
  --no-modify-path. Usar `. "$HOME/.cargo/env"` no terminal.
- Venv próprio da worktree, Python 3.11.16. Node 26.7.0/npm 11.19.0.
- Cargo.lock gerado e versionado. Versões diretas fixadas.
- MSRV declarado corrigido para 1.88 devido às transitivas time/time-core/time-macros;
  build efetivamente testado em 1.98.1, não em uma segunda toolchain 1.88.
- libc 0.2.189 (MIT OR Apache-2.0) promovida de transitiva a direta Unix para
  terminação do grupo de processos. Licença conferida no manifest local.
- Inventário completo: docs/dependencies.md. Sem dependência nova Python/JS.

## Implementado nesta execução
1. Compilação Tauri real, formatação Rust, Cargo.lock e permissão gerada pelo
   AppManifest versionados. Nenhuma capability foi ampliada.
2. Validação real de seletor, cancelamento inicial e de troca, preservação do
   rascunho, troca/reseleção, nome Unicode/espaços e mensagem controlada de erro.
3. Python/worker em grupo próprio Unix. Fechar janela ou sair durante inspeção
   aciona cancelamento, encerra só o grupo possuído e recolhe o child antes de sair.
   Timeout mantém o mesmo mecanismo. Nenhuma busca de processos por nome para kill.
4. Teste Rust de árvore sintética: worker termina; processo não relacionado continua.
5. Documentação de arquitetura, segurança, dependências e execução atualizada.

## Evidência nativa
- `npm run tauri -- dev`: compilou/lançou o binário real.
- A ferramenta de acessibilidade não reconhecia o executável avulso. Foi criado
  um invólucro LOCAL TEMPORÁRIO em `.cache/Prometeu Dev.app` apontando para o mesmo
  `target/debug/prometeu-desktop`, com PROMETEU_PYTHON do venv desta worktree.
  Não é instalador, não está no Git e não substitui IPC/Python por mocks.
- sample.pdf selecionado pelo diálogo nativo; resultado real exibido no React.
- Cópia idêntica “Amostra ação com espaços.pdf” também funcionou.
- PDF sintético inválido mostrou “PDF inválido ou malformado.”, sem stack.
- EMPTY real mostrou “Nenhum texto detectado”. SCANNED/MIXED cobertos nos testes
  frontend existentes; não foram apresentados como OCR suportado.
- Compilado também com `tauri build --debug --no-bundle` e override TEMPORÁRIO
  `.cache/tauri-800.json`: janela 800×600, assets em tauri://localhost, CSP de produção,
  Vite desligado. Inspeção e layout superior/inferior confirmados visualmente.
- Fixture longa sintética: 500 páginas. Channel exibiu “Analisando seu documento”.
  Observador local capturou app, bridge e worker ativos. Ao fechar a janela,
  os 3 processos desapareceram, 5,1 s após a captura (inclui tempo da interação UI).
  Evidência local: `.cache/lifecycle-observation.json`. Sem processo órfão observado.
- App e Vite encerrados após as verificações.

## Testes executados
### Python
Ruff check, Ruff format --check, mypy src/prometeu: passaram.
Última suíte: **123 passed**, 10,23 s. Nenhum módulo Python modificado nesta execução.
### Frontend
npm run lint, npm run typecheck, npm test, npm run build: passaram.
**11 testes**, 2 arquivos. Build final JS 235,72 kB (74,06 kB gzip), CSS 5,35 kB.
### Rust
cargo fmt --check e cargo check passaram sem warnings relevantes do aplicativo.
cargo test padrão passou; o teste com venv é explicitamente ignorado por padrão.
cargo test -- --include-ignored passou com **2 testes**, incluindo Python real e
limpeza de processos (0,52 s). Reexecução final --locked após ajuste de MSRV está
em andamento no momento desta gravação; registrar conclusão abaixo ao terminar.
Build nativo debug com assets locais e --no-bundle passou (25,33 s).

## Arquivos principais desta execução
- apps/desktop/src-tauri/src/main.rs: supervisão/fechamento e teste.
- apps/desktop/src-tauri/Cargo.toml e Cargo.lock: libc Unix e resolução fixa.
- apps/desktop/src-tauri/build.rs: rustfmt.
- apps/desktop/src-tauri/permissions/autogenerated/select_and_inspect_pdf.toml.
- README.md, SECURITY.md, apps/desktop/README.md, docs/dependencies.md,
  docs/frontend/architecture.md e este handoff.

## Ainda não implementado / riscos
Conversão GUI, capa, biblioteca persistente, abrir/localizar EPUB e instaladores.
Editora/data continuam rascunhos explícitos, não exportados pelo core.
PROMETEU_PYTHON é configuração confiável de desenvolvimento; release ainda recusa
inspeção até haver sidecar empacotado. Windows não suportado pelo adapter POSIX.
Linux, término forçado/crash externo do app, EPUBCheck e distribuição não validados.
Fechamento normal foi corrigido/testado; isso não é garantia de recuperação após
SIGKILL no próprio app. PNG transparente ainda é placeholder técnico.
Não houve teste da saída durante seletor modal aberto via Cmd+Q; cancelamento do
seletor funciona. Não abrir novas permissões para resolver eventuais problemas.

## Git e continuidade
Execução anterior: 1d37bca, e452d42, 3f25070, c25618e.
Segunda execução: `d0970cb` — fix: validate Tauri desktop inspection bridge.
O próximo commit preserva o ajuste de lifecycle e este fechamento.
Nenhum push/merge. As versões antigas deste handoff estão no histórico Git.

## Como retomar exatamente
1. Entrar em `.worktrees/desktop`; conferir branch/status/log; ler este handoff.
2. Ler apps/desktop/README.md e docs/frontend/architecture.md.
3. Ativar PATH do Rust. Em apps/desktop, definir
   `PROMETEU_PYTHON="$(cd ../.. && pwd)/.venv/bin/python"`.
4. `npm run tauri -- dev` abre o fluxo nativo já validado. Usar só fixtures sintéticas.
5. Próximo menor incremento: conversão GUI mínima reutilizando ConversionPipeline.run,
   com title/author/language/identifier já suportados; reinspecionar/snapshot na conversão.
   Não começar biblioteca, capa, metadados adicionais ou instaladores junto.

## Prompt sugerido
“Retome a worktree desktop lendo este handoff. O gate de inspeção nativa foi fechado.
Preserve o checkout principal. Implemente somente conversão GUI mínima pelo pipeline
Python existente, com saída segura e resultado explícito; não amplie outros recursos.”
