# Prometeu Desktop — Handoff

## Momento
Data: 2026-09-13. Branch: `integration/mvp`. HEAD inicial: `325e209`.
Marco: Gate A; inspeção inicial concluída, implementação ainda não iniciada.

## Objetivo desta sessão
Primeira fatia desktop até seleção e inspeção real de PDF com metadados editáveis
(Gate D). Conversão pela GUI somente após essa fatia testada e preservada.

## Estado encontrado
Árvore já modificada: README.md, SECURITY.md, docs/execution-status.md,
src/prometeu/cleaning/normalize.py, src/prometeu/structure/reconstruct.py,
tests/integration/test_conversion.py, tests/unit/test_epub_builder.py,
tests/unit/test_reconstruction_metadata.py. São alterações preexistentes de
normalização/reconstrução, regressões e documentação; autoria/sessão exata não
confirmada. Preservar e NÃO incluir nos commits desktop.
Não existe branch desktop. Não criar `feat/desktop-frontend` sobre árvore suja:
a condição do pedido não está satisfeita. Continuar no checkout atual, sem merge.

## Decisões arquiteturais
Core já expõe `ConversionPipeline.run` e `PdfPlumberExtractor.inspect` supervisionado.
React + TypeScript + Vite, Tauri 2; bridge de inspeção estreita, sem shell genérico.
Nenhuma dependência desktop nas dependências Python. Sem persistência nesta fatia.

## Implementado
Somente este handoff inicial.

## Parcialmente implementado
Nada ainda.

## Ainda não iniciado
Scaffold, GUI, bridge, testes e documentação de arquitetura.

## Arquivos criados
- docs/handoffs/frontend-desktop-handoff.md

## Arquivos alterados
Nenhum arquivo preexistente até este marco.

## Dependências adicionadas
Nenhuma ainda.

## Integração com o core / contratos
Inspecionar contratos existentes antes de implementar. Sem duplicar parsing de PDF.

## Comandos executados
`git branch --show-current`, `git status --short`, `git log --oneline --decorate -10`,
`git remote -v`, `git branch --list`, `git diff --stat`, buscas seletivas com `rg`,
leitura de README, pyproject, arquitetura, dependências, SECURITY, execução, CLI,
metadados e adapter. Node/npm disponíveis; cargo/rustc não encontrados no PATH.

## Testes executados
Nenhum ainda (Python/frontend/Rust).

## Testes não executados
Todos. Verificar toolchain antes de prometer build nativo.

## Resultados / problemas conhecidos / riscos
O MVP mais recente não pode ser presumido a partir de main. Alterações anteriores
permanecem na árvore. Metadados do core parecem limitados a título/autor/idioma;
confirmar suporte a editora/data sem inventar exportação.

## Segurança e privacidade
Usar apenas fixtures sintéticas. Não ler livros/anexos preexistentes. Não enviar
PDFs a serviços. Sem rede em runtime, telemetria ou CDN.

## Git
Nenhum commit desta sessão ainda. Nenhum push/merge/reset/stash.

## Como retomar
1. Executar status/log e ler este handoff.
2. Ler docs/frontend/architecture.md quando existir.
3. Conferir os contratos reais e concluir a menor fatia em andamento.
4. Testar e registrar resultados antes de iniciar conversão pela GUI.

## Próximo menor incremento recomendado
Fronteira pública de inspeção + scaffold desktop, seguido de UI e testes.

## Comando sugerido para a próxima sessão
“Continue a partir de docs/handoffs/frontend-desktop-handoff.md, preserve os oito
arquivos preexistentes e implemente apenas o próximo menor incremento testável.”

## Atualização Gate A/B — base isolada
Foi encontrada candidata mais recente: `2582b4d`, branch `codex/gate-e-mvp`, também
em origin. Ela NÃO coincide com a árvore suja inicial. Criada worktree isolada
`.worktrees/desktop` a partir dessa candidata, branch `feat/desktop-frontend`.
O handoff foi movido para essa worktree. Todo trabalho seguinte ocorre nela.
HEAD atual antes do primeiro commit: `2582b4d`. Os oito arquivos do checkout
principal continuam intocados; nenhum foi transportado para a nova branch.
Decisão: isolamento satisfaz preservação e fornece uma base limpa mais recente.
`docs/frontend/architecture.md` criado com escopo e contratos planejados.
Rust ausente inclusive em ~/.cargo/bin; não instalar toolchain nesta execução.
Fontes oficiais Tauri consultadas; versões/licenças npm consultadas antes de adicionar.
