import { Channel, invoke, isTauri } from '@tauri-apps/api/core';

export interface Inspection {
  file_name: string;
  page_count: number;
  kind: 'textual' | 'scanned' | 'mixed' | 'empty';
  metadata: { title: string; author: string | null; language: string };
  warnings: string[];
}

export interface ConversionMetadata {
  title: string;
  author: string;
  language: string;
  identifier: string;
}

export interface Conversion {
  output_path: string;
  pages: number;
  paragraphs: number;
  chapters: number;
  output_bytes: number;
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

export async function convertSelected(
  metadata: ConversionMetadata,
  onConverting: () => void,
): Promise<Conversion | null> {
  if (!isTauri()) {
    throw new Error('Para converter um PDF, abra o Prometeu no aplicativo desktop.');
  }
  const progress = new Channel<'converting'>();
  progress.onmessage = () => onConverting();
  try {
    return await invoke<Conversion | null>('convert_selected_pdf', { metadata, progress });
  } catch (error) {
    throw new Error(typeof error === 'string' ? error : 'Não foi possível converter este PDF.');
  }
}

export async function revealEpub(): Promise<void> {
  try {
    await invoke('reveal_epub');
  } catch (error) {
    throw new Error(typeof error === 'string' ? error : 'Não foi possível localizar o EPUB.');
  }
}
