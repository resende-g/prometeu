# Fixtures sintéticas

`sample.pdf` é uma obra original do projeto, distribuída sob a licença Apache-2.0
da raiz. Não contém texto, fontes ou dados de terceiros.

Regeneração determinística:

```sh
python -m tests.fixtures.generate
```

Conversão manual esperada quando o pipeline estiver implementado:

```sh
prometeu convert tests/fixtures/sample.pdf
```

O gerador usa fontes PDF Base 14 sem incorporação. O mapa `ToUnicode` torna o
texto não latino verificável na extração, mas não garante a aparência visual de
glifos fora de WinAnsi. Na primeira página, as linhas em `y=730` e `y=714`
pertencem ao mesmo parágrafo; o intervalo até `y=670` inicia outro parágrafo.
