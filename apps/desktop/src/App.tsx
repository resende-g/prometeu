import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, BookOpen, Check, FileText, LockKeyhole, Plus, TriangleAlert, Upload } from 'lucide-react';
import { convertSelected, revealEpub, selectAndInspect } from './desktop';
import type { Conversion, ConversionMetadata, Inspection } from './desktop';

type State =
  | { phase: 'library' | 'selecting' | 'inspecting' }
  | { phase: 'ready' | 'choosing-output' | 'converting'; inspection: Inspection; metadata: ConversionMetadata }
  | { phase: 'success'; conversion: Conversion }
  | { phase: 'inspection-error'; message: string }
  | { phase: 'conversion-error'; message: string; inspection: Inspection; metadata: ConversionMetadata };

const unsupported = {
  scanned: ['Documento digitalizado', 'Este PDF contém conteúdo visual sem texto extraível. O Prometeu ainda não oferece OCR para este tipo de documento.'],
  mixed: ['Documento com páginas sem texto', 'Este PDF mistura páginas com texto e páginas com conteúdo apenas visual. A conversão não é suportada nesta versão, pois poderia perder conteúdo. O Prometeu ainda não oferece OCR.'],
  empty: ['Nenhum texto detectado', 'Não foi encontrada uma camada de texto utilizável neste PDF. Escolha outro documento.'],
} as const;

export default function App() {
  const [state, setState] = useState<State>({ phase: 'library' });
  const inFlight = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const busy = ['selecting', 'inspecting', 'choosing-output', 'converting'].includes(state.phase);

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
          language: inspection.metadata.language, identifier: '' },
      } : previous);
    } catch (error) {
      setState({ phase: 'inspection-error', message: error instanceof Error ? error.message : 'Não foi possível inspecionar este PDF.' });
    } finally {
      inFlight.current = false;
    }
  }

  function edit(field: keyof ConversionMetadata, value: string) {
    setState(current => current.phase === 'ready'
      ? { ...current, metadata: { ...current.metadata, [field]: value } } : current);
  }

  async function convertPdf(inspection: Inspection, metadata: ConversionMetadata) {
    if (inFlight.current) return;
    inFlight.current = true;
    setState({ phase: 'choosing-output', inspection, metadata });
    try {
      const conversion = await convertSelected(metadata, () => setState({ phase: 'converting', inspection, metadata }));
      setState(conversion ? { phase: 'success', conversion } : { phase: 'ready', inspection, metadata });
    } catch (error) {
      setState({ phase: 'conversion-error', inspection, metadata, message: error instanceof Error ? error.message : 'Não foi possível converter este PDF.' });
    } finally {
      inFlight.current = false;
    }
  }

  async function reveal() {
    try {
      await revealEpub();
    } catch (error) {
      setState({ phase: 'inspection-error', message: error instanceof Error ? error.message : 'Não foi possível localizar o EPUB.' });
    }
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
          <p className="scope-note">Nesta prévia, você pode inspecionar e converter um PDF textual. A biblioteca persistente ainda não está disponível.</p>
        </> : <>
          {!busy && state.phase !== 'success' && <button className="back" onClick={() => setState({ phase: 'library' })}><ArrowLeft aria-hidden="true" size={17} />Biblioteca</button>}
          <div className="page-title"><div><p className="eyebrow">PDF PARA EPUB</p><h1 ref={heading} tabIndex={-1}>Nova conversão</h1></div></div>
          {busy && <section className="progress-state" role="status" aria-live="polite">
            <FileText aria-hidden="true" size={36} strokeWidth={1.3} />
            <h2>{state.phase === 'selecting' ? 'Escolha um PDF' : state.phase === 'inspecting' ? 'Analisando seu documento' : state.phase === 'choosing-output' ? 'Escolha onde salvar' : 'Convertendo para EPUB'}</h2>
            <p className="muted">{state.phase === 'selecting' || state.phase === 'choosing-output' ? 'Use a janela de seleção de arquivos.' : state.phase === 'inspecting' ? 'Verificando páginas e metadados. Isso pode levar alguns instantes.' : 'Extraindo e estruturando o texto, gerando e validando o EPUB.'}</p>
            {(state.phase === 'inspecting' || state.phase === 'converting') && <progress aria-label={`${state.phase === 'inspecting' ? 'Inspeção do PDF' : 'Conversão para EPUB'} em andamento`} />}
            <p className="small muted">O documento permanece neste computador.</p>
          </section>}
          {state.phase === 'inspection-error' && <section className="notice error" role="alert">
            <TriangleAlert aria-hidden="true" size={24} />
            <h2>Não foi possível analisar o PDF</h2><p>{state.message}</p>
            <button className="primary" onClick={selectPdf}>Escolher outro PDF</button>
          </section>}
          {state.phase === 'conversion-error' && <section className="notice error" role="alert">
            <TriangleAlert aria-hidden="true" size={24} />
            <h2>Não foi possível converter o PDF</h2><p>{state.message}</p>
            <button className="primary" onClick={() => convertPdf(state.inspection, state.metadata)}>Tentar novamente</button>
          </section>}
          {state.phase === 'success' && <section className="notice" role="status">
            <Check aria-hidden="true" size={24} />
            <h2>EPUB criado com sucesso</h2>
            <p><bdi>{state.conversion.output_path}</bdi></p>
            <p className="small muted">{state.conversion.pages} páginas · {state.conversion.chapters} capítulos · {state.conversion.paragraphs} parágrafos · {state.conversion.output_bytes} bytes</p>
            <div className="success-actions"><button className="primary" onClick={reveal}>Mostrar no Finder</button><button className="secondary" onClick={() => setState({ phase: 'library' })}>Converter outro PDF</button></div>
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
                    <label htmlFor="identifier">Identificador<input id="identifier" value={state.metadata.identifier} onChange={e => edit('identifier', e.target.value)} maxLength={1024} aria-describedby="identifier-help" placeholder="Gerado automaticamente se vazio" /></label>
                    <p id="identifier-help" className="small muted field-help">Use um identificador próprio ou deixe vazio para gerar um URN a partir do documento.</p>
                  </div>
                </section>
              </div>
              {state.inspection.warnings.length > 0 && <details className="warnings"><summary>Observações da inspeção ({state.inspection.warnings.length})</summary><ul>{state.inspection.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></details>}
              <div className="conversion-footer"><p id="conversion-help" className="small muted">O destino existente nunca será substituído.<br />Este rascunho é descartado ao voltar à biblioteca ou trocar o PDF.</p><button className="primary" onClick={() => convertPdf(state.inspection, state.metadata)} aria-describedby="conversion-help"><BookOpen aria-hidden="true" size={18} />Converter para EPUB</button></div>
            </>}
          </>}
        </>}
      </main>
      <footer className="privacy"><LockKeyhole aria-hidden="true" size={15} /><span>Processamento local <span className="privacy-detail">· Nenhum documento é enviado para servidores.</span></span></footer>
    </div>
  );
}
