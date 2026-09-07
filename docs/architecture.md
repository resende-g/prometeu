# Contratos — base da primeira fatia

PDF → inspeção → extração → PhysicalDocument → reconstrução → SemanticDocument
→ normalização → EPUBBuilder → validação do arquivo → publicação.

`document/model.py` contém valores próprios imutáveis. Páginas são consecutivas
desde 1; coordenadas em pontos, origem superior esquerda, x à direita/y para baixo.
Bounding boxes são finitas, sem inversão; dimensões de página/fontes são positivas.
Linhas textuais vêm de caracteres/texto, nunca de `page.lines` (traços gráficos).
IDs físicos: `p{pagina}-l{linha}` e `p{pagina}-l{linha}-s{span}`, índices desde 1.
O adapter devolve apenas estes tipos, nenhuma página/objeto externo.

Texto físico é derivado de spans preservados; texto semântico é derivado de runs.
Não existe campo de texto editável concorrente. `SourceReference.lines` permite
múltiplas páginas/linhas. Evidência física original permanece imutável e disponível
ao normalizador, que pode explicar alterações sem consultar novamente o PDF.

Capítulo guarda H1 opcional em `heading`, renderizado uma única vez. `blocks`
contém parágrafos e H2/H3 em ordem de leitura. Estes headings delimitam seções
implicitamente; não há árvore duplicada. Navegação constrói hierarquia por níveis
do modelo. Capítulo sem heading não inventa título visível. IDs semânticos estáveis
derivam da origem, com prefixos por tipo. Confidence é escore, não probabilidade.

Exemplo: duas linhas `p1-l2` e `p2-l1` podem formar `Paragraph(id='para-p1-l2',
runs=(Inline('Texto contínuo'),), source=SourceReference((LineOrigin(1,'p1-l2'),
LineOrigin(2,'p2-l1'))))`. A decisão usa posição/estilo/pontuação e permanece testável
sem PDF. Limpeza de margens confirmadas exige recompor continuidade com essas origens.

## Interfaces estabilizadas

`document/contracts.py`: request, limites, inspeção, diagnósticos, estatísticas,
resultados/erros, opções e três Protocols explicitamente requeridos pelo projeto.

- `PDFExtractor.inspect(path, limits)` precede `extract(path, inspection, limits)`.
  Owner E implementa `extraction/pdfplumber_adapter.py:PdfPlumberExtractor` e
  supervisão de processo também para inspeção; IPC JSON limitado, não pickle.
- `EPUBExporter.export(semantic, path, ExportOptions)` escreve apenas temporário
  fornecido pelo P. Owner X: `epub/builder.py:EPUBBuilder`.
- `EPUBValidator.validate(path, limits)` reabre arquivo, devolve status explícito.
  Owner X: `validation/internal.py:InternalEPUBValidator`.
- Owner P: `structure/reconstruct.py:reconstruct(physical, metadata)` retorna
  ReconstructionResult; `cleaning/normalize.py:normalize(semantic, physical)`
  retorna NormalizationResult. Application `ConversionPipeline.run(request)`
  coordena dependências concretas; CLI somente argumentos/apresentação.

Erros: entrada=2, tipo não suportado=3, extração=4, exportação=5, validação=6;
falha não classificada=1. Diagnósticos usam códigos estáveis e texto compreensível.
Validação ausente é NOT_RUN, nunca PASSED. Resultado só publica caminho no sucesso.

Limites padrão: entrada/saída 50 MiB, 500 páginas, 5 milhões de caracteres,
120 s de parede/CPU e 1 GiB de memória. Plataforma e mecanismos aplicados precisam
ser reportados. Metadados: override → PDF válido → inferência conservadora →
título genérico; autor ausente; idioma `und` com diagnóstico; identificador por
hash do conteúdo (sem caminho pessoal). Texto incompatível com XML falha com código,
sem remoção silenciosa. Nenhum download/serviço em runtime.
