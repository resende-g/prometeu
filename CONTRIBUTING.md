# Contribuição

Use Python 3.11+ e o ambiente isolado descrito no README. Execute Ruff lint/format,
mypy estrito, pytest e build antes de entregar um pacote de trabalho. Cada mudança
de comportamento exige teste; regressões devem ser reproduzidas antes da correção.

Preserve alterações alheias e use commits locais pequenos, com caminhos explícitos.
Não versione livros, documentos reais, logs de conteúdo ou segredos. Fixtures devem
ser sintéticas originais, com gerador e expectativa revisável independente.

O domínio não importa parser/CLI/exporter. Mudanças nos contratos exigem reconciliar
todos os consumidores; não criar um segundo modelo nem dependência sem análise.
Contribuições intencionais ao código original seguem Apache-2.0 (LICENSE).

Nenhuma publicação ou push faz parte da execução local atual. A matriz de CI não
é evidência de execução remota bem-sucedida.
