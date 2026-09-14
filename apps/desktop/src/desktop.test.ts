import { expect, it } from 'vitest';
import { convertSelected, selectAndInspect } from './desktop';

it('a prévia no navegador não simula seleção ou inspeção nativa', async () => {
  await expect(selectAndInspect(() => { throw new Error('Não deve inspecionar'); }))
    .rejects.toThrow('apenas a prévia da interface');
});

it('a prévia no navegador não simula conversão nativa', async () => {
  await expect(convertSelected(
    { title: 'T', author: '', language: 'pt-BR', identifier: '' },
    () => { throw new Error('Não deve converter'); },
  )).rejects.toThrow('aplicativo desktop');
});
