import { Channel, invoke, isTauri } from '@tauri-apps/api/core';

export interface Inspection {
  file_name: string;
  page_count: number;
  kind: 'textual' | 'scanned' | 'mixed' | 'empty';
  metadata: { title: string; author: string | null; language: string };
  warnings: string[];
}

export async function selectAndInspect(onInspecting: () => void): Promise<Inspection | null> {
  if (!isTauri()) {
    throw new Error('Para selecionar um PDF, abra o Prometeu no aplicativo desktop. Esta é apenas a prévia da interface.');
  }
  const progress = new Channel<'inspecting'>();
  progress.onmessage = () => onInspecting();
  try {
    return await invoke<Inspection | null>('select_and_inspect_pdf', { progress });
  } catch (error) {
    // O shell devolve mensagens controladas; objetos inesperados não chegam à tela.
    throw new Error(typeof error === 'string' ? error : 'Não foi possível inspecionar este PDF.');
  }
}
