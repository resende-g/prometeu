import { useEffect, useRef, useState } from 'react';
import { ArrowRight, BookOpen, Check, FilePlus2, FileText, FolderOpen, Library, LockKeyhole, Plus, RefreshCw, Settings, TriangleAlert } from 'lucide-react';
import { convertSelected, revealEpub, selectAndInspect } from './desktop';
import type { Conversion, ConversionMetadata, Inspection } from './desktop';
import prometeuLogo from './assets/prometeu-logo.png';

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
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><img src={prometeuLogo} alt="" /><span>PROMETEU</span></div>
        <nav aria-label="Navegação principal">
          <button className={`nav-item ${state.phase === 'library' ? 'active' : ''}`} onClick={() => setState({ phase: 'library' })} aria-current={state.phase === 'library' ? 'page' : undefined}>
            <Library aria-hidden="true" size={18} />Biblioteca
          </button>
          <button className={`nav-item ${state.phase !== 'library' ? 'active' : ''}`} onClick={selectPdf} disabled={busy} aria-current={state.phase !== 'library' ? 'page' : undefined}>
            <FilePlus2 aria-hidden="true" size={18} />Nova conversão
          </button>
          <button className="nav-item" disabled title="Disponível em uma próxima versão">
            <Settings aria-hidden="true" size={18} />Configurações
          </button>
        </nav>
        <div className="sidebar-signature">
          <img src={prometeuLogo} alt="" />
          <p>Transformando conhecimento<br />em liberdade.</p>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <span>Local. Livre. Sem limites.</span>
          <span className="preview-badge">Desktop alpha</span>
        </header>
        <main aria-busy={busy}>
          {state.phase === 'library' ? <>
            <div className="page-title">
              <div><p className="eyebrow">SUA BIBLIOTECA LOCAL</p><h1 ref={heading} tabIndex={-1}>Seus livros</h1></div>
              <button className="primary" onClick={selectPdf}><Plus aria-hidden="true" size={18} />Converter PDF</button>
            </div>
            <section className="empty-state" aria-labelledby="empty-title">
              <img className="hero-logo" src={prometeuLogo} alt="" />
              <h2 id="empty-title">Bem-vindo ao Prometeu</h2>
              <p className="muted">Transforme seu PDF em um livro digital.</p>
              <p className="privacy-copy">Seus documentos permanecem neste computador.<br />Nenhum arquivo é enviado para servidores.</p>
              <button className="primary hero-action" onClick={selectPdf}><FilePlus2 aria-hidden="true" size={18} />Selecionar PDF</button>
              <p className="small muted">PDFs com texto selecionável · Sem OCR</p>
              <div className="format-path"><span><FileText aria-hidden="true" size={16} />PDF</span><ArrowRight aria-hidden="true" size={16} /><span><BookOpen aria-hidden="true" size={16} />EPUB</span></div>
            </section>
            <p className="scope-note">A biblioteca persistente ainda não está disponível nesta prévia.</p>
          </> : <>
            <div className="page-title"><div><p className="eyebrow">PDF PARA EPUB</p><h1 ref={heading} tabIndex={-1}>Nova conversão</h1></div></div>
            {busy && <section className="progress-state" role="status" aria-live="polite">
              <div className="progress-icon"><FileText aria-hidden="true" size={30} strokeWidth={1.4} /></div>
              <h2>{state.phase === 'selecting' ? 'Escolha um PDF' : state.phase === 'inspecting' ? 'Analisando seu documento…' : state.phase === 'choosing-output' ? 'Escolha onde salvar' : 'Criando seu livro digital…'}</h2>
              <p className="muted">{state.phase === 'selecting' || state.phase === 'choosing-output' ? 'Use a janela de seleção de arquivos.' : state.phase === 'inspecting' ? 'Estamos verificando as informações do PDF.' : 'Extraindo e organizando o conteúdo para gerar o EPUB.'}</p>
              {(state.phase === 'inspecting' || state.phase === 'converting') && <progress aria-label={`${state.phase === 'inspecting' ? 'Inspeção do PDF' : 'Conversão para EPUB'} em andamento`} />}
              <div className="stage-list" aria-hidden="true">
                {state.phase === 'converting' && <span className="done"><Check size={15} />PDF analisado</span>}
                <span className="current"><span className="stage-dot" />{state.phase === 'converting' ? 'Criando e validando o EPUB' : state.phase === 'inspecting' ? 'Lendo páginas e metadados' : state.phase === 'choosing-output' ? 'Definindo o destino' : 'Aguardando sua escolha'}</span>
              </div>
              <p className="local-note"><LockKeyhole aria-hidden="true" size={15} />O documento permanece neste computador.</p>
            </section>}
            {state.phase === 'inspection-error' && <section className="notice error" role="alert">
              <TriangleAlert aria-hidden="true" size={26} />
              <h2>Não foi possível analisar o PDF</h2><p>{state.message}</p>
              <button className="primary" onClick={selectPdf}>Escolher outro PDF</button>
            </section>}
            {state.phase === 'conversion-error' && <section className="notice error" role="alert">
              <TriangleAlert aria-hidden="true" size={26} />
              <h2>Não foi possível converter o PDF</h2><p>{state.message}</p>
              <button className="primary" onClick={() => convertPdf(state.inspection, state.metadata)}>Tentar novamente</button>
            </section>}
            {state.phase === 'success' && <section className="success-state" role="status">
              <div className="success-check"><Check aria-hidden="true" size={30} /></div>
              <h2>Seu EPUB está pronto!</h2>
              <p className="success-title">{state.conversion.chapters} {state.conversion.chapters === 1 ? 'capítulo' : 'capítulos'} convertido{state.conversion.chapters === 1 ? '' : 's'}</p>
              <div className="validation-result"><Check aria-hidden="true" size={18} /><span><strong>EPUB verificado</strong><small>{state.conversion.pages} páginas · {state.conversion.paragraphs} parágrafos · {state.conversion.output_bytes} bytes</small></span></div>
              <p className="output-path"><bdi>{state.conversion.output_path}</bdi></p>
              <div className="success-actions"><button className="primary" onClick={reveal}><FolderOpen aria-hidden="true" size={18} />Mostrar no Finder</button><button className="secondary" onClick={() => setState({ phase: 'library' })}><RefreshCw aria-hidden="true" size={17} />Converter outro PDF</button></div>
            </section>}
            {state.phase === 'ready' && <>
              <section className="document-row" aria-label="PDF selecionado">
                <span className="file-icon"><FileText aria-hidden="true" size={24} strokeWidth={1.4} /></span>
                <div className="file-info"><strong><bdi>{state.inspection.file_name}</bdi></strong><p className="small muted">{state.inspection.page_count} {state.inspection.page_count === 1 ? 'página' : 'páginas'} · {state.inspection.kind === 'textual' ? 'PDF textual' : 'Inspeção concluída'}</p></div>
                <button className="secondary compact" onClick={selectPdf}>Trocar arquivo</button>
              </section>
              {state.inspection.kind !== 'textual' ? <section className="notice" role="status">
                <TriangleAlert aria-hidden="true" size={26} />
                <h2>{unsupported[state.inspection.kind][0]}</h2><p>{unsupported[state.inspection.kind][1]}</p>
                <button className="primary" onClick={selectPdf}>Escolher outro PDF</button>
              </section> : <>
                <p className="inspection-status"><Check aria-hidden="true" size={17} />Documento pronto para conversão</p>
                <div className="metadata-layout">
                  <aside className="cover-area" aria-label="Prévia da capa">
                    <h2>Capa</h2>
                    <div className="cover-placeholder"><span className="cover-mark">PROMETEU</span><strong>{state.metadata.title || 'Sem título'}</strong><span>{state.metadata.author || 'Autor não informado'}</span></div>
                    <p className="small muted">Prévia tipográfica. Capas personalizadas chegam em uma próxima versão.</p>
                  </aside>
                  <section aria-labelledby="metadata-title">
                    <h2 id="metadata-title">Metadados</h2>
                    <p className="small muted form-intro">Revise os dados encontrados no PDF.</p>
                    <div className="fields">
                      <label htmlFor="title">Título<input id="title" value={state.metadata.title} onChange={e => edit('title', e.target.value)} maxLength={512} /></label>
                      <label htmlFor="author">Autor<input id="author" value={state.metadata.author} onChange={e => edit('author', e.target.value)} maxLength={512} placeholder="Nome do autor" /></label>
                      <div className="field-pair">
                        <label htmlFor="language">Idioma<input id="language" value={state.metadata.language} onChange={e => edit('language', e.target.value)} maxLength={63} list="languages" aria-describedby="language-help" /></label>
                        <label htmlFor="identifier">Identificador<input id="identifier" value={state.metadata.identifier} onChange={e => edit('identifier', e.target.value)} maxLength={1024} aria-describedby="identifier-help" placeholder="Gerado se vazio" /></label>
                      </div>
                      <datalist id="languages"><option value="pt-BR">Português (Brasil)</option><option value="pt-PT">Português (Portugal)</option><option value="en">Inglês</option><option value="es">Espanhol</option><option value="und">Não identificado</option></datalist>
                      <p id="language-help" className="visually-hidden">Use pt-BR para português do Brasil. “und” significa idioma não identificado.</p>
                      <p id="identifier-help" className="small muted field-help">Deixe o identificador vazio para gerar um URN automaticamente.</p>
                    </div>
                  </section>
                </div>
                {state.inspection.warnings.length > 0 && <details className="warnings"><summary>Observações da inspeção ({state.inspection.warnings.length})</summary><ul>{state.inspection.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></details>}
                <div className="conversion-footer"><p id="conversion-help" className="small muted">O destino existente nunca será substituído.</p><button className="primary" onClick={() => convertPdf(state.inspection, state.metadata)} aria-describedby="conversion-help">Converter para EPUB<ArrowRight aria-hidden="true" size={18} /></button></div>
              </>}
            </>}
          </>}
        </main>
        <footer className="privacy"><LockKeyhole aria-hidden="true" size={14} /><span>Processamento local <span className="privacy-detail">· Nenhum documento é enviado para servidores.</span></span></footer>
      </div>
    </div>
  );
}
