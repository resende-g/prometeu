import { expect, it } from 'vitest';
import { selectAndInspect } from './desktop';

it('a prévia no navegador não simula seleção ou inspeção nativa', async () => {
  await expect(selectAndInspect(() => { throw new Error('Não deve inspecionar'); }))
    .rejects.toThrow('apenas a prévia da interface');
});
