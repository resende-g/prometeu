# Política de segurança

## Sistema e fronteiras

Prometeu é uma aplicação local que lê PDF não confiável e publica EPUB local.
Entrada, texto, metadados, links e estrutura do PDF são controláveis por atacante.
Configuração da CLI e executável/JAR de EPUBCheck são fornecidos pelo usuário.
Não há backend, conta, endpoint público ou envio de documentos.

## Invariantes exigidas

- Inspeção e parsing devem ocorrer em processo supervisionado com limites finitos,
  timeout que encerra o processo e limites de memória/CPU onde suportados.
- Nunca executar ações, JavaScript ou anexos do PDF; não desserializar pickle da entrada.
- Rejeitar criptografia e conteúdo relevante não extraível neste MVP sem OCR.
- Nunca sobrescrever entrada ou alias. Saída existente falha por padrão; validar
  temporário antes da publicação atômica e preservar não sobrescrita em corridas.
- XML estruturado, DTD/entidades proibidas, sem scripts, handlers ou recursos remotos.
- Conversão não usa rede, telemetria, histórico ou cache documental persistente.
- Logs normais mostram etapas/contagens/códigos, sem texto integral ou controles de terminal.

## Achados reportáveis

Execução de código, exfiltração, path traversal, escrita arbitrária, perda silenciosa
de conteúdo, destruição de entrada/saída anterior e limites ineficazes são problemas
relevantes. O adapter não é sandbox. Testes não provam ausência de vulnerabilidades.
Não há exclusão de classes de falha nem risco de segurança aceito implicitamente.

## Estado e limitações

Na Wave 1, inspeção e extração usam subprocessos encerrados e recolhidos pelo
supervisor em timeout, excesso de memória ou IPC. No macOS, o controle de memória
é RSS por libproc, amostrado nominalmente a cada 20 ms; não é uma reserva rígida
e pode haver excesso entre amostras. RLIMIT_CPU limita o worker; RLIMIT_AS só é
usado no Linux. A matriz final executou Linux real em container somente leitura,
sem rede, limitado por cgroup a 2 GiB, 2 CPUs e 256 processos; isso comprova o
comportamento observado nessa configuração, não constitui sandbox contra kernel ou
runtime comprometido. A aplicação requer o processo principal em macOS/Linux para
o prazo por SIGALRM. O prazo inclui snapshot, processamento, validação e fsync,
terminando antes da publicação atômica; não há garantia de prazo para um syscall de
filesystem bloqueado pelo sistema.

A entrada é aberta, verificada e copiada para diretório privado. A publicação
sem sobrescrita usa `os.link`: um destino concorrente nunca é substituído.
`--force` usa `os.replace`, sem seguir symlinks ou escrever no inode anterior.
Mudanças observadas até a última checagem cancelam a publicação, mas POSIX rename
não oferece comparação e troca: um escritor externo que mude o destino entre
essa checagem e o rename pode ter seu destino substituído. A proteção contra
aliases vale para o estado verificado; não cobre mutação adversarial simultânea
do namespace por outro processo com permissão de escrita. Para coordenação
estrita entre escritores, use saída distinta e sem `--force`.

O validador reabre o ZIP com limites de tamanho/entradas, proíbe DTD, entidades,
instruções de processamento e conteúdo fora do perfil XHTML/CSS gerado. A revisão
independente do diff terminou sem bloqueantes, e o artefato sintético passou no
EPUBCheck 5.3.0 e no Kindle Previewer 4.0.0. Essas evidências não substituem uma
auditoria de segurança nem provam ausência de vulnerabilidades. O estado verificado
está em docs/execution-status.md. Vulnerabilidades desconhecidas de dependências
continuam possíveis; processamento nunca deve ocorrer com privilégios elevados.
Não se promete remoção de temporários após falha irrecuperável do sistema.

Não há canal privado de reporte configurado nem contato de segurança inventado.
Antes de divulgar uma vulnerabilidade, combine um canal com o mantenedor; não
publique documentos privados nem detalhes desnecessários de exploração.
