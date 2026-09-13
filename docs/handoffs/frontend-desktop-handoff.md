# Prometeu Desktop — Handoff

## Momento
Data: 2026-09-13. Branch: `feat/desktop-frontend`.
Worktree: `.worktrees/desktop` do repositório principal.
HEAD de implementação verificado: `3f25070`. O commit documental que contém este
fechamento sucede esse HEAD; obter seu hash com `git rev-parse HEAD` na worktree.

## Objetivo desta sessão
Primeira fatia até biblioteca vazia, seleção/inspeção e metadados editáveis.
Gates A–C concluídos; Gate D implementado nos componentes, porém ainda sem
validação ponta a ponta no shell nativo. Gate E (conversão GUI) não iniciado.
Gate F: verificações Python/frontend concluídas; Rust bloqueado por toolchain ausente.

## Estado encontrado e preservado
Checkout inicial: `integration/mvp`, HEAD `325e209`, oito arquivos já modificados:
README.md, SECURITY.md, docs/execution-status.md,
src/prometeu/cleaning/normalize.py, src/prometeu/structure/reconstruct.py,
tests/integration/test_conversion.py, tests/unit/test_epub_builder.py,
tests/unit/test_reconstruction_metadata.py. Alterações de reconstrução/normalização,
regressões e documentação; autoria/sessão exata não comprovada.

Encontrada candidata posterior `2582b4d` em `codex/gate-e-mvp` e origin, diferente
da árvore suja inicial. Criada worktree limpa a partir dela, na branch solicitada.
Não houve reset, stash, descarte, merge ou push. Os oito arquivos originais ficaram
intocados: status/diffstat inicial e final iguais (418 inserções, 28 remoções).
A documentação alterada nesta branch é a cópia isolada, não a cópia suja original.

## Decisões arquiteturais
React/TypeScript/Vite + CSS simples + Lucide; Tauri 2 apenas para janela, seleção
e IPC. Python conserva toda a lógica de PDF/metadados. Sem banco/persistência
antes de haver conversão GUI. Sem percentual fictício, arrastar/soltar ou controles
que aparentem converter. Editora/data são rascunhos explícitos, pois o core só
suporta título/autor/idioma/identificador. Capa fica como placeholder informativo.

## Implementado
- Biblioteca vazia, wordmark PROMETEU, identidade em cinzas e privacidade visível.
- Tela Nova conversão, nome/páginas/tipo, edição de cinco campos e observações.
- Estados explícitos library/selecting/inspecting/ready/error; cancelar mantém
  rascunho; trocar PDF/voltar descarta com aviso. Seleção concorrente bloqueada.
- Estados textual/scanned/mixed/empty preservados do core. Sem promessa de OCR.
- API pública `application.inspection.inspect_document(path, limits)`.
- Bridge Python com JSON limitado, validação de pedido, erros sem stack/conteúdo.
- Código de seletor nativo/Channel/IPC/execução Python no Rust e capability mínima.
- Testes Python/React e teste Rust da fixture, este último ainda não executado.

## Parcialmente implementado
Shell e integração nativa escritos, sem build/teste manual. Interpretador em
PROMETEU_PYTHON (absoluto, confiável, somente debug). Release recusa inspeção;
sidecar/distribuição não resolvidos. Windows recusado na bridge porque o adapter
existente usa mecanismos POSIX; não foi criada uma alternativa sem supervisão.

## Ainda não iniciado
Conversão GUI, capa, progresso por etapa de conversão, biblioteca JSON, busca,
abrir/localizar EPUB, instaladores. Não há livro demo no fluxo de produção.

## Arquivos criados
- `apps/desktop/`: package.json/lock, HTML, tsconfig, Vite, ESLint, README e .gitignore.
- `apps/desktop/src/`: App.tsx, desktop.ts, main.tsx, styles.css, dois arquivos de teste.
- `apps/desktop/src-tauri/`: Cargo.toml, build.rs, tauri.conf.json,
  capabilities/main.json, src/main.rs e icons/icon.png.
- `src/prometeu/application/inspection.py`, `desktop_inspect.py`.
- `tests/integration/test_desktop_inspection.py`.
- `docs/frontend/architecture.md` e este handoff.

## Arquivos alterados
README.md, SECURITY.md e docs/dependencies.md, somente na worktree desktop.
Nenhum módulo maduro do core foi alterado em relação à candidata `2582b4d`.

## Dependências adicionadas
Versões, finalidade, licença e necessidade de TODAS as dependências diretas estão
na seção Desktop de `docs/dependencies.md`. Resumo:

| Dependência | Versão | Licença |
| --- | --- | --- |
| React / React DOM | 19.3.0 | MIT |
| TypeScript | 6.0.3 | Apache-2.0 |
| Vite / plugin-react | 8.3.0 / 6.1.1 | MIT |
| Lucide React | 1.45.0 | ISC |
| Tauri API / CLI | 2.11.1 / 2.11.4 | Apache-2.0 OR MIT |
| tauri / tauri-build / dialog | 2.11.5 / 2.6.3 / 2.7.3 | Apache-2.0 OR MIT |
| serde / serde_json | 1.0.229 / 1.0.151 | MIT OR Apache-2.0 |
| Vitest / Testing Library React | 5.0.0 / 16.3.3 | MIT |

Também adicionados tipos, jsdom, user-event e lint conforme inventário completo.
Licenças npm confirmadas em package.json/LICENSE locais; Rust em crates.io.
TypeScript 7 foi rejeitado por conflito de peer; 6.0.3 instalado sem --force.
package-lock.json versionado; Cargo.lock ainda não gerado. Nenhuma dependência
Python adicionada, nem Node/React/Rust ao wheel. Avisos transitivos de distribuição
nativa ainda precisam de revisão após resolução Cargo e antes de instaladores.

## Integração com o core / contratos definidos
`select_and_inspect_pdf(progress: Channel)` não recebe caminhos nem executáveis.
Rust abre o diálogo e chama argv fixo `Python -I -m prometeu.application.desktop_inspect`.
Stdin aceita somente `{ "path": caminho_absoluto_pdf }`, máximo 16 KiB.
Resposta `{ok:true, inspection:{file_name,page_count,kind,metadata,warnings}}` ou
`{ok:false,error:{code,message}}`; Rust limita leitura a 64 KiB e prazo a 130 s.
Metadados title/author/language usam `resolve_metadata` existente. A API chama
`PdfPlumberExtractor.inspect` com limites existentes (padrão 120 s, 50 MiB,
500 páginas); não chama extract/reconstruct/export. Nenhum caminho absoluto é
retornado à UI. Futura conversão precisa reinspecionar/snapshot, pois o arquivo
pode mudar após a seleção.

## Comandos executados
- Inventário inicial/final: git branch/status/log/remote/diff/worktree, leituras com rg.
- `git worktree add .worktrees/desktop -b feat/desktop-frontend 2582b4d`.
- Ambiente Python próprio via uv venv e uv pip install -c constraints.txt -e '.[dev]'.
- npm view e consulta crates.io para versões/licenças, npm install.
- Comandos de testes abaixo; `npm exec tauri info`; Vite + navegador local.
- Prévia e servidor temporários encerrados após verificação visual.

## Testes executados
### Python
- `.venv/bin/python -m ruff check .`: passou.
- `.venv/bin/python -m ruff format --check .`: 48 arquivos conformes.
- `.venv/bin/python -m mypy src/prometeu`: passou, 23 arquivos.
- `.venv/bin/python -m pytest -q`: **123 passed**, 8,35 s.
- Foco inicial dos testes novos: 14 passed, 3,78 s, incluindo bridge real com -I,
  limite de entrada, pedidos inválidos, caminhos Unicode/com caracteres de shell,
  cancelamento de extração proibida no teste e metadados inválidos.
- `.venv/bin/python -m build`: wheel e sdist produzidos com sucesso.
- CLI instalada `--help` e `convert tests/fixtures/sample.pdf -o <temporário>`:
  sucesso; 2 páginas, 4 parágrafos, EPUB de 2.496 bytes; validação interna passou,
  EPUBCheck NOT_RUN. Saída sintética temporária removida ao terminar a checagem.

### Frontend
`npm run lint`, `npm run typecheck`, `npm test`, `npm run build`: passaram.
11 testes em 2 arquivos: vazio, seleção/edição, cancelamento, troca, progresso,
SCANNED/MIXED/EMPTY, erro/retentativa, texto não confiável e prévia sem mock nativo.
Build final: JS 235,72 kB (74,06 kB gzip), CSS 5,35 kB.
Biblioteca/erro conferidos visualmente em 800×600, com rolagem vertical normal.
Formulário validado por testes DOM; ainda não inspecionado visualmente no Tauri.

### Tauri / Rust
`npm exec tauri info`: reconheceu a configuração; reportou ausência de cargo,
rustc e rustup. Seu exit 0 é do diagnóstico, NÃO significa build nativo aprovado.
Nenhuma toolchain grande instalada. Fontes oficiais confirmaram exigência de PNG
RGBA em generate_context; placeholder transparente adicionado, sem nova logo.
CSP dev permite inline para o preâmbulo/refresh Vite; produção permanece estrita.

## Testes não executados
cargo check, cargo fmt --check, cargo test, seletor/Channel/CSP no shell real,
fechamento da janela durante inspeção, Linux/Windows, Python 3.12/3.13,
EPUBCheck, instaladores e verificação com rede bloqueada pelo sistema operacional.

## Resultados / problemas conhecidos / riscos
A fatia está commitada e testada nas partes disponíveis; NÃO é instalador pronto.
Sem Rust não há garantia de compilação/funcionamento da integração nativa. Corrigir
primeiro qualquer falha de cargo ou IPC antes de ampliar funcionalidade. Resolver e
versionar Cargo.lock. Não há cancelamento de inspeção: fechar a janela pode deixar
o Python terminar a operação; revisar ciclo de vida antes de distribuir.
PNG transparente é requisito técnico temporário e precisa do asset oficial.

## Segurança e privacidade
Somente fixtures sintéticas usadas. Nenhum livro preexistente foi lido/enviado.
Sem telemetria, CDN, backend remoto, upload, shell genérico ou filesystem exposto.
Uma capability da janela main permite só o comando específico. Sem logging integral
de documentos ou persistência de PDFs. Instalação usou registries oficiais; o
runtime criado não faz consultas externas. Adapter continua não sendo sandbox.

## Git
Commits desta sessão, até o fechamento documental:
- `1d37bca` docs: define desktop frontend architecture and handoff (antes da implementação).
- `e452d42` feat: expose bounded desktop PDF inspection bridge.
- `3f25070` feat: add desktop inspection UI and Tauri shell.
Handoff atualizado entre Gates A/B, B/C, C/D e F; histórico está nos commits.
Sem push ou merge. Checkout principal ainda em integration/mvp com os oito diffs.

## Como retomar
1. Entrar na worktree `.worktrees/desktop`; executar git status/log e ler este arquivo.
2. Ler `apps/desktop/README.md` e `docs/frontend/architecture.md`.
3. Com Rust estável e pré-requisitos Tauri disponíveis, na pasta apps/desktop:
   definir PROMETEU_PYTHON para o Python absoluto do venv DESTA worktree;
   executar cargo check/fmt/test pelos comandos do README; resolver Cargo.lock.
4. `npm run tauri -- dev`; selecionar sample.pdf sintético, cancelar/trocar,
   editar metadados, confirmar estágio real, mensagens e layout em 800×600.
5. Só após esse fluxo validado, integrar ConversionPipeline.run com os campos
   já suportados, sem duplicar lógica. Estender contratos Python antes de prometer
   exportação de editora/data/capa; publicar saída com as garantias atuais do core.

## Próximo menor incremento recomendado
Compilar e exercitar o seletor + inspeção no Tauri, corrigir integração e versionar
Cargo.lock. Depois, conversão real mínima pela GUI. Não começar biblioteca persistente
ou instaladores antes disso.

## Comando sugerido para a próxima sessão
“Retome a worktree .worktrees/desktop, branch feat/desktop-frontend, lendo
este handoff. Preserve o checkout principal sujo. Valide e corrija a integração
Tauri/Python com a fixture sintética; não amplie o escopo antes de fechar esse fluxo.”

## Segunda execução — início (2026-09-13)
HEAD inicial: `c25618e0ba8f546f5f2797d9f27feb220309ba78`.
Branch feat/desktop-frontend; worktree limpa. Objetivo: fechar compilação Tauri,
seletor nativo e inspeção real da fixture até React antes de qualquer conversão.
Rust/cargo/rustup continuam ausentes do PATH e ~/.cargo/bin. Node/npm disponíveis;
Xcode Command Line Tools em /Library/Developer/CommandLineTools.
Próxima ação: instalar Rust estável mínimo pela fonte oficial, incluindo rustfmt,
sem alterar perfil do shell; compilar o scaffold existente e corrigir erros reais.
Checkout principal não será alterado. Conversão permanece fora do trabalho ativo.

### Segunda execução — toolchain instalado
Rust 1.98.1, cargo 1.98.1, rustup 1.29.1 instalados para aarch64-apple-darwin
via https://sh.rustup.rs, perfil minimal + rustfmt, --no-modify-path. Sem alteração
de configuração do shell. Usar ~/.cargo/bin no PATH dos comandos de desenvolvimento.
Python -I no cwd do intérprete deste venv retornou sample.pdf real (2 páginas,
textual, título Amostra sintética). Suítes nesta execução: 123 testes Python e
11 frontend passaram; lint/tipagem/build frontend e Ruff/mypy passaram.
Fmt inicial encontrou apenas formatação; cargo fmt aplicado. cargo check em
andamento, log local ignorado em .cache/cargo-check.log. Nenhuma conversão GUI.

### Segunda execução — compilação aprovada
cargo fmt --check passou após formatação; cargo check passou em 1m05s, sem erros
ou warnings do aplicativo. Cargo.lock gerado. cargo test e teste explícito ignorado
(que invoca Python real) em andamento. O seletor/IPC ainda precisam do teste visual
nativo; não considerar o gate fechado apenas com compilação.

### Segunda execução — inspeção nativa real aprovada parcialmente
cargo test padrão passou (teste dependente de venv ignorado por configuração);
cargo test -- --ignored passou: 1 teste real, 0,32 s. Tauri dev compilou/lançou.
Para controle nativo por acessibilidade foi necessário um invólucro .app TEMPORÁRIO
em .cache/Prometeu Dev.app, usando o MESMO target/debug/prometeu-desktop e o venv
da worktree. Não é instalador, não está versionado e não muda IPC/core.
Janela nativa aberta: seletor real abriu sample.pdf, Python real retornou ao React
nome, 2 páginas, tipo textual, título Amostra sintética e autor da fixture.
Edição de título/idioma, cancelamento inicial e cancelamento de troca preservando
rascunho foram confirmados. Cópia sintética com espaços/Unicode também funcionou;
PDF sintético inválido retornou mensagem controlada sem stack. Ferramenta de UI
exigiu ação acessível `open` nos ícones do diálogo, em vez de clique simples.
Faltam fechar verificação 800×600 e ciclo de vida em inspeção longa. Conversão GUI
não iniciada. Nenhuma capability foi ampliada.
