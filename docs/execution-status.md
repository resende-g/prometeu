# Prometeu — execução local

Data: 2026-09-07. Branch: integration/mvp. Wave 0 concluída; Gate A aprovado.
Comandos e resultados em [gates.md](gates.md).

## Fontes e lacunas

Leitura integral concluída: 01 visão, 02 arquitetura, 04 modelo, 05 casos de uso,
06 qualidade, 07 licenças, 08 segurança, 09 roadmap, 10 backlog, prompt mestre
Prometeu - MVP.md e Fundacaodoprojeto.md. Este último é o roteiro dos dez documentos.
Os oito PDFs técnicos foram lidos localmente com PDFKit: cinco guias EPUBCheck,
visão EPUB 3, pdfplumber/PyPI e pdfminer.six. Comandos antigos são referências,
não versões aprovadas. Livros em PDFs_test não foram analisados nem incorporados.

O 03 na raiz duplica 02, SHA-256
58abc3303a44ff8b20f64833d939576c95f4959d80533baf7d84597973c5c862.
A fonte correta fornecida depois, Downloads/03 - Requisitos Funcionais e Não
Funcionais.md, inicia pelo título correto e foi lida integralmente: 32.068 bytes,
SHA-256 90920e287c915cb4d0af039fc068f5a7f0677b3609762103a81e7a2c6033369b.
O bloqueio anterior está resolvido; o original errado permanece intocado.

Não havia AGENTS.md local/ancestral aplicável, README, LICENSE, SECURITY,
CONTRIBUTING, código ou Git. Instruções AGENTS fornecidas na conversa aplicadas.
PNG mencionado no mestre não localizado: lacuna não bloqueante ao núcleo textual.
Licença de redistribuição dos anexos não presumida; ficam fora do Git.

## Decisões e divergências

O prompt de execução fixa notas sem associação, imagens sem exportação, nenhum OCR,
IA ou GUI, mesmo onde fontes mais amplas os preveem. Não se marcam esses RF como
concluídos. Requisitos corretos prevalecem sobre exemplos da arquitetura/backlog.
Árvore de seções: headings H2/H3 ordenados delimitam seções sem duplicar a estrutura.

## Plano operacional e ownership

| Onda | Owner | Aceite |
| --- | --- | --- |
| 0 | P: bootstrap, modelos, contratos, configurações/docs | Gate A real, commits pequenos |
| 1 | E: input/extraction; X: epub/validation; Q: fixtures/integration; P: structure/application/CLI | Primeiro PDF → dois modelos → EPUB validado; Gate B |
| 2 | P: semântica; X: nav; Q: positivos/negativos | Parágrafos, continuidade, headings, capítulos, TOC; Gate C |
| 3 | E: margens após transferência explícita; P: normalização; X: validação; Q: regressões | Limpeza conservadora/Unicode/segurança; Gate D |
| 4 | R independente; P integra correções | Gate E, wheel limpo, execução offline, relatório |

E/X/Q só após Gate A e commit de contratos. Até quatro implementadores contando P.
Worktrees isolados preferidos. Especialistas Sol/high e revisor Astra/high conforme
pedido. Nenhum agente especializado iniciado antes do Gate A.
Cada pacote: revisar diff → integrar → Ruff → mypy → pytest → corrigir → avançar.

## Ambiente e evidências iniciais

macOS 26.6.2 arm64; Python inicial 3.14.7; Git 2.55.0. Git inicial ausente
(exit 128); inicialização local integration/mvp realizada (exit 0) após permissão
do ambiente. uv 0.12.10 instalado somente em .tools (exit 0), para instalar Python
3.11.16, 3.12.14 e 3.13.15 em .python (exit 0). Java launcher sem runtime (exit 1).
EPUBCheck não executado. Compatibilidade Kindle não verificada manualmente.
Workflow configurado; execução remota não verificada. Não houve publicação remota.

## Próximos passos

Lançar pacotes independentes após o commit dos contratos. Conversão ainda não implementada.
