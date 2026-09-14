# Prometeu Desktop alpha

React/TypeScript → Tauri IPC → `application.inspection.inspect_document` →
`PdfPlumberExtractor.inspect` ou `ConversionPipeline.run` → worker supervisionado
do core → EPUB validado e publicado.

## Escopo
Biblioteca vazia, seleção nativa de PDF, inspeção real, edição de título, autor,
idioma e identificador, conversão real, resultado explícito e localização no Finder.
Capa, editora/data, persistência e instalador funcional não são implementados.

## Fronteira
Três comandos IPC específicos: `select_and_inspect_pdf`, `convert_selected_pdf` e
`reveal_epub`. Seletores nativos ficam no Rust; JavaScript não fornece caminhos,
executáveis nem comandos. Rust retém entrada e última saída em memória, inicia o
Python por argv fixo e envia JSON limitado em stdin. Inspeção reutiliza a API
pública; conversão chama diretamente `ConversionPipeline.run` com `overwrite=False`.
O frontend fornece somente quatro metadados não confiáveis, revalidados pelo bridge
e pelo core. `reveal_epub` usa `/usr/bin/open -R` apenas no macOS e apenas com a
última saída retida pelo Rust.
Python/worker são lançados em grupo próprio. Fechar/sair durante processamento
sinaliza somente esse grupo, recolhe o child e então encerra a janela/app.
O mesmo mecanismo atende timeout; nenhum processo é buscado por nome.
Parsing continua em Python com os limites e supervisão existentes. O adapter é
isolamento de processo, não sandbox; seu suporte atual é macOS/Linux.

Apenas a janela main possui permissões individuais. Não há plugin shell, filesystem,
HTTP ou opener exposto ao JavaScript. CSP local, sem origens remotas; script/style inline somente na CSP de
desenvolvimento para o refresh do Vite. Produção mantém CSP estrita. Servidor Vite
somente em loopback durante desenvolvimento. Metadados renderizados como texto.

## Desenvolvimento e distribuição
Tauri 2 + React + Vite, CSS simples, ícones Lucide locais. O shell usa intérprete
absoluto em `PROMETEU_PYTHON`, fornecido pelo desenvolvedor e somente em builds debug.
Nunca recebe esse valor da UI. Python/core devem estar instalados nesse ambiente.
Builds release recusam inspeção e conversão até haver sidecar empacotado; não distribuir esta
fatia como instalador funcional. Nenhum caminho pessoal fica no código.
A integração foi compilada e validada em macOS arm64/Rust 1.98.1. Seletor
nativo → Python → React foi exercitado com a fixture sintética, incluindo
cancelamento, Unicode/espaços, erro e layout 800×600. Cargo.lock versionado.

## Estado e armazenamento
Estado discriminado: library → selecting → inspecting → ready → choosing-output →
converting → success ou erro controlado. Cancelar um seletor preserva o formulário
anterior. Uma operação por vez; nenhuma porcentagem simulada. Metadados e caminhos
da sessão ficam apenas em memória nesta versão.
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

Empacotar Python/core como sidecar offline para tornar o build release utilizável.
Não adicionar editora/data/capa antes de estender e testar os contratos do core.
