# Prometeu — estado de execução

Data: 2026-09-11. Branch `codex/gate-e-mvp`; código verificado no commit
`2582b4de371de859d7ac41b106d7eb480304ea2d`.

## Estado final

**Gates A–E: 5/5. MVP: 100% do escopo definido.**

| Gate | Estado | Evidência principal |
| --- | --- | --- |
| A | Concluído | Bootstrap, contratos e build fixado |
| B | Concluído | Pipeline textual, validação interna e publicação atômica |
| C | Concluído | Continuidade, H1/H2/H3, capítulos, anchors e TOC |
| D | Concluído | Margens, paginação, deshifenização e NFC semântico |
| E | Concluído | Revisão independente e toda a matriz local/externa |

## Evidência final

| Verificação | Numerador/denominador ou contagem | Exit code | Resultado |
| --- | ---: | ---: | --- |
| macOS/Python 3.11.16 | 109/109 testes | 0 | Passou |
| macOS/Python 3.12.14 | 109/109 testes | 0 | Passou |
| macOS/Python 3.13.15 | 109/109 testes | 0 | Passou |
| Ruff 0.16.6 | 44 arquivos; 0 achados | 0 | Passou |
| mypy 2.3.1 | 21 arquivos; 0 erros | 0 | Passou |
| Build 1.6.0/setuptools 84.0.0 | wheel + sdist | 0 | Passou |
| Wheel limpo/Python 3.13.15 | import + 2/2 helps | 0 | Passou |
| Linux/Python 3.12.13 | 109/109 testes + ferramentas | 0 | Passou |
| EPUBCheck 5.3.0 | 0 erros; 0 warnings | 0 | Passou |
| Kindle Previewer 4.0.0 | 0 erros; 0 problemas de qualidade | 0 | Passou |
| GitHub Actions | 6/6 jobs | 0 | Passou |
| Revisão independente | 7/7 contraprovas finais | — | Zero bloqueantes |

O Linux foi executado em Alpine 3.23.5/aarch64, container somente leitura e sem
rede, com cgroup de 2 GiB, 2 CPUs e 256 processos. O Kindle abriu o KPF e confirmou
capítulos, ordem, TOC H1/H2/H3, Unicode, negrito, itálico e conteúdo limpo. O aviso
W14016 de capa ausente é não bloqueante; capas e imagens estão fora do MVP.

O workflow hospedado
[34642131348](https://github.com/resende-g/prometeu/actions/runs/34642131348)
executou em Ubuntu e macOS com Python 3.11, 3.12 e 3.13, sobre exatamente o SHA
`2582b4de371de859d7ac41b106d7eb480304ea2d`. Os seis jobs concluíram com
`success`.

Comandos, versões, hashes dos artefatos e limites observados estão detalhados em
[gates.md](gates.md).

## Escopo encerrado

O MVP converte PDF textual simples, de uma coluna, em EPUB 3 reflowable. OCR, notas
de rodapé, layouts multicoluna, imagens, IA, GUI e associação de notas permanecem
fora do escopo. A validação do EPUB sintético não generaliza para todo PDF
arbitrário, e o adapter não constitui sandbox.

## Estado Git

O commit de código verificado foi enviado a `origin/codex/gate-e-mvp`; esta
consolidação documental registra as evidências obtidas depois dele.
`docs/handoff-next-slice.md` continua não rastreado e intacto por descrever o
estado anterior a `2582b4d`.
