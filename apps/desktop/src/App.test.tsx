import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { convertSelected, revealEpub, selectAndInspect } from './desktop';
import type { Conversion, Inspection } from './desktop';

vi.mock('./desktop', () => ({ selectAndInspect: vi.fn(), convertSelected: vi.fn(), revealEpub: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
const inspect = vi.mocked(selectAndInspect);
const convert = vi.mocked(convertSelected);
const reveal = vi.mocked(revealEpub);
const sample: Inspection = {
  file_name: 'amostra sintética.pdf', page_count: 2, kind: 'textual',
  metadata: { title: 'Livro sintético', author: 'Autor fictício', language: 'pt-BR' },
  warnings: [],
};
const conversion: Conversion = {
  output_path: '/tmp/livro sintético.epub', pages: 2, paragraphs: 4, chapters: 1, output_bytes: 2048,
};

async function select(result: Inspection | null = sample) {
  inspect.mockResolvedValueOnce(result);
  const user = userEvent.setup();
  render(<App />);
  await user.click(screen.getByRole('button', { name: 'Selecionar PDF' }));
  return user;
}

describe('primeira fatia desktop', () => {
  it('mostra biblioteca vazia, privacidade e escopo real', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: 'Seus livros' })).toBeTruthy();
    expect(screen.getByText(/Nenhum documento é enviado/)).toBeTruthy();
    expect(screen.getByText(/biblioteca persistente ainda não/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Abrir EPUB' })).toBeNull();
  });

  it('inspeciona e permite editar somente os quatro metadados exportáveis', async () => {
    const user = await select();
    expect(screen.getByText('amostra sintética.pdf')).toBeTruthy();
    expect(screen.getByText('2 páginas · PDF textual')).toBeTruthy();
    expect((screen.getByLabelText('Título') as HTMLInputElement).value).toBe('Livro sintético');
    expect((screen.getByLabelText('Autor') as HTMLInputElement).value).toBe('Autor fictício');
    for (const [label, value] of [['Título', 'Novo título'], ['Autor', 'Outro autor'], ['Idioma', 'es'], ['Identificador', 'urn:teste:1']]) {
      const input = screen.getByLabelText(label) as HTMLInputElement;
      await user.clear(input);
      await user.type(input, value);
      expect(input.value).toBe(value);
    }
    expect((screen.getByRole('button', { name: 'Converter para EPUB' }) as HTMLButtonElement).disabled).toBe(false);
    expect(screen.queryByLabelText('Editora')).toBeNull();
    expect(screen.queryByLabelText('Data')).toBeNull();
  });

  it.each(['scanned', 'mixed', 'empty'] as const)('explica documento %s sem oferecer conversão', async kind => {
    await select({ ...sample, kind });
    expect(screen.getByRole('status')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Escolher outro PDF' })).toBeTruthy();
    expect(screen.queryByLabelText('Título')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Converter para EPUB' })).toBeNull();
    if (kind !== 'empty') expect(screen.getByText(/ainda não oferece OCR/)).toBeTruthy();
  });

  it('preserva rascunho se o seletor for cancelado e limpa ao trocar o PDF', async () => {
    const user = await select();
    await user.clear(screen.getByLabelText('Título'));
    await user.type(screen.getByLabelText('Título'), 'Rascunho');
    inspect.mockResolvedValueOnce(null);
    await user.click(screen.getByRole('button', { name: 'Trocar arquivo' }));
    expect((screen.getByLabelText('Título') as HTMLInputElement).value).toBe('Rascunho');
    inspect.mockResolvedValueOnce({ ...sample, metadata: { ...sample.metadata, title: 'Segundo PDF' } });
    await user.click(screen.getByRole('button', { name: 'Trocar arquivo' }));
    expect((screen.getByLabelText('Título') as HTMLInputElement).value).toBe('Segundo PDF');
  });

  it('cancelar a primeira seleção retorna à biblioteca', async () => {
    await select(null);
    expect(screen.getByRole('heading', { name: 'Seus livros' })).toBeTruthy();
  });

  it('usa evento real de inspeção e progresso indeterminado, impedindo seleção concorrente', async () => {
    let complete!: (inspection: Inspection) => void;
    inspect.mockImplementationOnce(onInspecting => {
      onInspecting();
      return new Promise(resolve => { complete = resolve; });
    });
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole('button', { name: 'Selecionar PDF' }));
    expect(screen.getByRole('heading', { name: /Analisando seu documento/ })).toBeTruthy();
    expect(screen.getByRole('progressbar').hasAttribute('value')).toBe(false);
    expect(screen.queryByRole('button', { name: 'Selecionar PDF' })).toBeNull();
    await act(async () => complete(sample));
    expect(inspect).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText('Título')).toBeTruthy();
  });

  it('apresenta erro e permite nova tentativa', async () => {
    inspect.mockRejectedValueOnce(new Error('PDF inválido ou malformado.'));
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole('button', { name: 'Selecionar PDF' }));
    expect(screen.getByRole('alert').textContent).toContain('PDF inválido ou malformado.');
    inspect.mockResolvedValueOnce(sample);
    await user.click(screen.getByRole('button', { name: 'Escolher outro PDF' }));
    expect(screen.getByLabelText('Título')).toBeTruthy();
  });

  it('mantém metadados não confiáveis como texto e descarta rascunho ao voltar', async () => {
    const user = await select({ ...sample, metadata: { ...sample.metadata, title: '<img src=x onerror=alert(1)>' }, warnings: ['<script>não executar</script>'] });
    expect(document.querySelector('main img, main script')).toBeNull();
    expect(screen.getByText('<script>não executar</script>')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Biblioteca' }));
    expect(screen.getByRole('heading', { name: 'Seus livros' })).toBeTruthy();
    expect(screen.queryByLabelText('Título')).toBeNull();
  });

  it('converte pelo bridge real da interface, mostra resultado e localiza o EPUB', async () => {
    const user = await select();
    convert.mockImplementationOnce((_metadata, onConverting) => {
      onConverting();
      return Promise.resolve(conversion);
    });
    reveal.mockResolvedValueOnce();
    await user.click(screen.getByRole('button', { name: 'Converter para EPUB' }));
    expect(convert).toHaveBeenCalledWith(
      { title: 'Livro sintético', author: 'Autor fictício', language: 'pt-BR', identifier: '' },
      expect.any(Function),
    );
    expect(screen.getByRole('status').textContent).toContain('Seu EPUB está pronto!');
    expect(screen.getByText('/tmp/livro sintético.epub')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Mostrar no Finder' }));
    expect(reveal).toHaveBeenCalledOnce();
  });

  it('preserva metadados ao cancelar destino ou repetir conversão após erro', async () => {
    const user = await select();
    await user.clear(screen.getByLabelText('Título'));
    await user.type(screen.getByLabelText('Título'), 'Rascunho');
    convert.mockResolvedValueOnce(null);
    await user.click(screen.getByRole('button', { name: 'Converter para EPUB' }));
    expect((screen.getByLabelText('Título') as HTMLInputElement).value).toBe('Rascunho');
    convert.mockRejectedValueOnce(new Error('O destino já existe.'));
    await user.click(screen.getByRole('button', { name: 'Converter para EPUB' }));
    expect(screen.getByRole('alert').textContent).toContain('O destino já existe.');
    convert.mockResolvedValueOnce(conversion);
    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(screen.getByRole('status').textContent).toContain('Seu EPUB está pronto!');
  });
});
