import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, BookOpen, Check, FileText, LockKeyhole, Plus, TriangleAlert, Upload } from 'lucide-react';
import { selectAndInspect } from './desktop';
import type { Inspection } from './desktop';

type Metadata = { title: string; author: string; language: string; publisher: string; date: string };
type State =
  | { phase: 'library' | 'selecting' | 'inspecting' }
  | { phase: 'ready'; inspection: Inspection; metadata: Metadata }
  | { phase: 'error'; message: string };

const unsupported = {
  scanned: ['Documento digitalizado', 'Este PDF contém conteúdo visual sem texto extraível. O Prometeu ainda não oferece OCR para este tipo de documento.'],
  mixed: ['Documento com páginas sem texto', 'Este PDF mistura páginas com texto e páginas com conteúdo apenas visual. A conversão não é suportada nesta versão, pois poderia perder conteúdo. O Prometeu ainda não oferece OCR.'],
  empty: ['Nenhum texto detectado', 'Não foi encontrada uma camada de texto utilizável neste PDF. Escolha outro documento.'],
} as const;

export default function App() {
  const [state, setState] = useState<State>({ phase: 'library' });
  const inFlight = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const busy = state.phase === 'selecting' || state.phase === 'inspecting';

  useEffect(() => { heading.current?.focus(); }, [state.phase]);

  async function selectPdf() {
    if (inFlight.current) return;
    inFlight.current = true;
    const previous = state;
    setState({ phase: 'selecting' });
    try {
      const inspection = await selectAndInspect(() => setState({ phase: 'inspecting' }));
      setState(inspection ? {
        phase: 'ready', inspection,
        metadata: { title: inspection.metadata.title, author: inspection.metadata.author ?? '',
          language: inspection.metadata.language, publisher: '', date: '' },
      } : previous);
    } catch (error) {
      setState({ phase: 'error', message: error instanceof Error ? error.message : 'Não foi possível inspecionar este PDF.' });
    } finally {
      inFlight.current = false;
    }
  }

  function edit(field: keyof Metadata, value: string) {
    setState(current => current.phase === 'ready'
      ? { ...current, metadata: { ...current.metadata, [field]: value } } : current);
  }

  return (
    <div className="app">
      <header className="topbar">
        <span className="wordmark">PROMETEU</span>
        <span className="edition">Desktop <span className="preview-badge">Prévia</span></span>
      </header>
      <main aria-busy={busy}>
        {state.phase === 'library' ? <>
          <div className="page-title">
            <div><p className="eyebrow">SUA BIBLIOTECA LOCAL</p><h1 ref={heading} tabIndex={-1}>Seus livros</h1></div>
            <button className="primary" onClick={selectPdf}><Plus aria-hidden="true" size={18} />Converter PDF</button>
          </div>
          <section className="empty-state" aria-labelledby="empty-title">
            <div className="book-symbol"><BookOpen aria-hidden="true" size={52} strokeWidth={1.1} /></div>
            <p className="eyebrow">DO DOCUMENTO À LEITURA</p>
            <h2 id="empty-title">Transforme seu PDF<br />em um livro digital</h2>
            <p className="muted">Seus documentos permanecem neste computador.</p>
            <button className="primary" onClick={selectPdf}><Upload aria-hidden="true" size={18} />Selecionar PDF</button>
            <p className="small muted">PDFs com texto selecionável · Sem OCR</p>
            <div className="format-path"><span><FileText aria-hidden="true" size={16} />PDF</span><ArrowRight aria-hidden="true" size={16} /><span><BookOpen aria-hidden="true" size={16} />EPUB</span></div>
          </section>
          <p className="scope-note">Nesta prévia, você pode inspecionar um PDF e revisar os metadados. A conversão e o armazenamento de livros ainda não estão disponíveis.</p>
        </> : <>
          {!busy && <button className="back" onClick={() => setState({ phase: 'library' })}><ArrowLeft aria-hidden="true" size={17} />Biblioteca</button>}
          <div className="page-title"><div><p className="eyebrow">PDF PARA EPUB</p><h1 ref={heading} tabIndex={-1}>Nova conversão</h1></div></div>
          {busy && <section className="progress-state" role="status" aria-live="polite">
            <FileText aria-hidden="true" size={36} strokeWidth={1.3} />
            <h2>{state.phase === 'selecting' ? 'Escolha um PDF' : 'Analisando seu documento'}</h2>
            <p className="muted">{state.phase === 'selecting' ? 'Use a janela de seleção de arquivos.' : 'Verificando páginas e metadados. Isso pode levar alguns instantes.'}</p>
            {state.phase === 'inspecting' && <progress aria-label="Inspeção do PDF em andamento" />}
            <p className="small muted">O documento permanece neste computador.</p>
          </section>}
          {state.phase === 'error' && <section className="notice error" role="alert">
            <TriangleAlert aria-hidden="true" size={24} />
            <h2>Não foi possível analisar o PDF</h2><p>{state.message}</p>
            <button className="primary" onClick={selectPdf}>Escolher outro PDF</button>
          </section>}
          {state.phase === 'ready' && <>
            <section className="document-row" aria-label="PDF selecionado">
              <FileText aria-hidden="true" size={28} strokeWidth={1.4} />
              <div className="file-info"><strong><bdi>{state.inspection.file_name}</bdi></strong><p className="small muted">{state.inspection.page_count} {state.inspection.page_count === 1 ? 'página' : 'páginas'} · {state.inspection.kind === 'textual' ? 'PDF textual' : 'Inspeção concluída'}</p></div>
              <button className="secondary" onClick={selectPdf}>Trocar arquivo</button>
            </section>
            {state.inspection.kind !== 'textual' ? <section className="notice" role="status">
              <TriangleAlert aria-hidden="true" size={24} />
              <h2>{unsupported[state.inspection.kind][0]}</h2><p>{unsupported[state.inspection.kind][1]}</p>
              <button className="primary" onClick={selectPdf}>Escolher outro PDF</button>
            </section> : <>
              <p className="inspection-status"><Check aria-hidden="true" size={18} />Texto detectado · Metadados disponíveis para revisão</p>
              <div className="metadata-layout">
                <aside className="cover-area" aria-label="Capa">
                  <div className="cover-placeholder"><BookOpen aria-hidden="true" size={38} strokeWidth={1.2} /><span>Sem capa</span></div>
                  <p className="small muted">A inclusão de capa estará disponível em uma próxima versão.</p>
                </aside>
                <section aria-labelledby="metadata-title">
                  <p className="eyebrow">DETALHES DO LIVRO</p><h2 id="metadata-title">Metadados</h2>
                  <p className="small muted form-intro">Revise as informações disponíveis no PDF. Campos ausentes podem ser preenchidos.</p>
                  <div className="fields">
                    <label htmlFor="title">Título<input id="title" value={state.metadata.title} onChange={e => edit('title', e.target.value)} maxLength={512} /></label>
                    <label htmlFor="author">Autor<input id="author" value={state.metadata.author} onChange={e => edit('author', e.target.value)} maxLength={512} placeholder="Nome do autor" /></label>
                    <label htmlFor="language">Idioma<input id="language" value={state.metadata.language} onChange={e => edit('language', e.target.value)} maxLength={63} list="languages" aria-describedby="language-help" /></label>
                    <datalist id="languages"><option value="pt-BR">Português (Brasil)</option><option value="pt-PT">Português (Portugal)</option><option value="en">Inglês</option><option value="es">Espanhol</option><option value="und">Não identificado</option></datalist>
                    <p id="language-help" className="small muted field-help">Use pt-BR para português do Brasil. “und” significa idioma não identificado.</p>
                    <div className="field-pair">
                      <label htmlFor="publisher">Editora<input id="publisher" value={state.metadata.publisher} onChange={e => edit('publisher', e.target.value)} maxLength={512} aria-describedby="draft-help" placeholder="Opcional" /></label>
                      <label htmlFor="date">Data<input id="date" type="date" value={state.metadata.date} onChange={e => edit('date', e.target.value)} aria-describedby="draft-help" /></label>
                    </div>
                    <p id="draft-help" className="small muted field-help">Editora e data são apenas rascunhos; a exportação desses campos ainda não é suportada.</p>
                  </div>
                </section>
              </div>
              {state.inspection.warnings.length > 0 && <details className="warnings"><summary>Observações da inspeção ({state.inspection.warnings.length})</summary><ul>{state.inspection.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></details>}
              <div className="conversion-footer"><p id="conversion-help" className="small muted">A conversão pela interface ainda não está disponível.<br />Este rascunho é descartado ao voltar à biblioteca ou trocar o PDF.</p><button className="primary" disabled aria-describedby="conversion-help"><BookOpen aria-hidden="true" size={18} />Converter para EPUB</button></div>
            </>}
          </>}
        </>}
      </main>
      <footer className="privacy"><LockKeyhole aria-hidden="true" size={15} /><span>Processamento local <span className="privacy-detail">· Nenhum documento é enviado para servidores.</span></span></footer>
    </div>
  );
}
