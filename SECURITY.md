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

Na Wave 0 as invariantes acima são requisitos, não controles concluídos. O estado
verificado está em docs/execution-status.md. Vulnerabilidades desconhecidas de
dependências continuam possíveis; processamento nunca deve ocorrer com privilégios
elevados. Não se promete remoção de temporários após falha irrecuperável do sistema.

Não há canal privado de reporte configurado nem contato de segurança inventado.
Antes de divulgar uma vulnerabilidade, combine um canal com o mantenedor; não
publique documentos privados nem detalhes desnecessários de exploração.
