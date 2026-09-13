# Prometeu Desktop — primeira fatia

React/TypeScript → Tauri IPC → `application.inspection.inspect_document` →
`PdfPlumberExtractor.inspect` → worker supervisionado do core.

## Escopo
Biblioteca vazia, seleção nativa de PDF, inspeção real e edição de título, autor,
idioma, editora e data. Editora/data são rascunhos explícitos, sem suporte atual no
core. Conversão, capa, persistência e abertura de saídas ainda não implementadas.
Nenhuma ação de conversão fictícia. Sem extração completa para preencher a tela.

## Fronteira
Um único comando IPC: `select_and_inspect_pdf`, com um Channel de progresso e
sem parâmetros de caminho ou comando. O seletor nativo
fica no Rust; JavaScript não fornece caminhos, executáveis nem comandos. Rust
inicia o Python por argv fixo (`-I -m prometeu.application.desktop_inspect`) e envia
um objeto JSON em stdin. Esse módulo só aceita inspeção e reutiliza a API pública.
Parsing continua em Python com os limites e supervisão existentes. O adapter é
isolamento de processo, não sandbox; seu suporte atual é macOS/Linux.

Apenas a janela main possui a permissão do comando. Não há plugin shell, filesystem,
HTTP ou opener exposto ao JavaScript. CSP local, sem origens remotas; script/style inline somente na CSP de
desenvolvimento para o refresh do Vite. Produção mantém CSP estrita. Servidor Vite
somente em loopback durante desenvolvimento. Metadados renderizados como texto.

## Desenvolvimento e distribuição
Tauri 2 + React + Vite, CSS simples, ícones Lucide locais. O shell usa intérprete
absoluto em `PROMETEU_PYTHON`, fornecido pelo desenvolvedor e somente em builds debug.
Nunca recebe esse valor da UI. Python/core devem estar instalados nesse ambiente.
Builds release recusam inspeção até haver sidecar empacotado; não distribuir esta
fatia como instalador funcional. Nenhum caminho pessoal fica no código.
Rust ausente no ambiente inicial: build nativo e teste do seletor ficam pendentes.

## Estado e armazenamento
Estado discriminado: library → selecting → inspecting → ready ou error.
Cancelar seleção preserva o formulário anterior. Uma inspeção por vez; nenhuma
porcentagem simulada. Metadados editados ficam apenas em memória nesta versão.
Ao voltar à biblioteca, o rascunho é descartado, com aviso visível.
Biblioteca persistente futura: JSON no diretório de dados do app (Tauri), escrito
atomicamente; só adicionar quando conversão real produzir itens. Não copiar PDFs
nem armazenar o texto extraído. Não há índice fictício ou livro demo em produção.

## Privacidade e licenças
Sem conta, backend remoto, telemetria, fontes/CDNs ou consultas bibliográficas.
Instalação de dependências pode usar rede; inspeção e uso instalado não precisam.
A CLI e o wheel Python permanecem independentes de Node/Rust/React.
Wordmark PROMETEU provisório; futuro asset oficial em `apps/desktop/src/assets/`.
O PNG transparente em src-tauri/icons é somente requisito de generate_context;
não representa nova logo. Substituir antes da distribuição.

## Fontes técnicas consultadas
- [Diálogo nativo Tauri](https://v2.tauri.app/plugin/dialog/)
- [Capabilities e AppManifest](https://v2.tauri.app/security/capabilities/)

## Próximo incremento
Validar cargo check/test e seletor nativo em macOS; em seguida integrar
`ConversionPipeline.run` sem alterar o pipeline. Reinspecionar/snapshot na conversão;
a seleção anterior não garante que o arquivo permaneceu igual. Não prometer
editora/data/capa até estender e testar contratos e exportação Python.
