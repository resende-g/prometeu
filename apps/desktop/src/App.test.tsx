import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { selectAndInspect } from './desktop';
import type { Inspection } from './desktop';

vi.mock('./desktop', () => ({ selectAndInspect: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
const inspect = vi.mocked(selectAndInspect);
const sample: Inspection = {
  file_name: 'amostra sintética.pdf', page_count: 2, kind: 'textual',
  metadata: { title: 'Livro sintético', author: 'Autor fictício', language: 'pt-BR' },
  warnings: [],
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
    expect(screen.getByText(/conversão e o armazenamento de livros ainda não/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Abrir EPUB' })).toBeNull();
  });

  it('inspeciona e permite editar os cinco metadados sem fingir conversão', async () => {
    const user = await select();
    expect(screen.getByText('amostra sintética.pdf')).toBeTruthy();
    expect(screen.getByText('2 páginas · PDF textual')).toBeTruthy();
    expect((screen.getByLabelText('Título') as HTMLInputElement).value).toBe('Livro sintético');
    expect((screen.getByLabelText('Autor') as HTMLInputElement).value).toBe('Autor fictício');
    for (const [label, value] of [['Título', 'Novo título'], ['Autor', 'Outro autor'], ['Idioma', 'es'], ['Editora', 'Editora fictícia'], ['Data', '2026-09-13']]) {
      const input = screen.getByLabelText(label) as HTMLInputElement;
      await user.clear(input);
      await user.type(input, value);
      expect(input.value).toBe(value);
    }
    expect((screen.getByRole('button', { name: 'Converter para EPUB' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/Editora e data são apenas rascunhos/)).toBeTruthy();
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
    expect(screen.getByRole('heading', { name: 'Analisando seu documento' })).toBeTruthy();
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
});
