#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
#[cfg(unix)]
use std::os::unix::process::CommandExt;
use std::{
    io::{Read, Write},
    path::PathBuf,
    process::{Command, ExitStatus, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    time::{Duration, Instant},
};
use tauri::{ipc::Channel, Manager, State};
use tauri_plugin_dialog::DialogExt;

const BRIDGE_ERROR: &str =
    "Não foi possível executar o processamento local. Verifique a instalação do Prometeu.";
const MAX_REPLY: u64 = 64 * 1024;
const MAX_REQUEST: usize = 32 * 1024;

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "lowercase")]
enum DocumentKind {
    Textual,
    Scanned,
    Mixed,
    Empty,
}

#[derive(Deserialize, Serialize)]
struct Metadata {
    title: String,
    author: Option<String>,
    language: String,
}

#[derive(Deserialize, Serialize)]
struct Inspection {
    file_name: String,
    page_count: u32,
    kind: DocumentKind,
    metadata: Metadata,
    warnings: Vec<String>,
}

#[derive(Deserialize)]
struct BridgeError {
    message: String,
}

#[derive(Deserialize)]
struct Reply {
    ok: bool,
    inspection: Option<Inspection>,
    error: Option<BridgeError>,
}

#[derive(Deserialize)]
struct ConversionMetadata {
    title: String,
    author: String,
    language: String,
    identifier: String,
}

#[derive(Deserialize, Serialize)]
struct Conversion {
    output_path: String,
    pages: u32,
    paragraphs: u32,
    chapters: u32,
    output_bytes: u64,
}

#[derive(Deserialize)]
struct ConversionReply {
    ok: bool,
    conversion: Option<Conversion>,
    error: Option<BridgeError>,
}

#[derive(Default)]
struct InspectionState {
    busy: AtomicBool,
    closing: AtomicBool,
    selected: Mutex<Option<PathBuf>>,
    output: Mutex<Option<PathBuf>>,
}

// Só recebe um child ainda não recolhido, lançado em seu próprio grupo (process_group(0)).
fn stop_child(child: &mut std::process::Child) {
    #[cfg(unix)]
    // SAFETY: id é do child possuído e não recolhido; seu PGID foi definido no spawn.
    // O sinal alcança exclusivamente esse grupo e seus workers, sem busca por nome/PID externo.
    unsafe {
        libc::kill(-(child.id() as i32), libc::SIGKILL);
    }
    let _ = child.kill();
    let _ = child.wait();
}

fn run_bridge(
    module: &str,
    request: Vec<u8>,
    closing: &AtomicBool,
    interrupted: &'static str,
    timed_out: &'static str,
) -> Result<(ExitStatus, Vec<u8>), String> {
    // ponytail: intérprete de desenvolvimento; substituir por sidecar antes de distribuir.
    if !cfg!(debug_assertions) {
        return Err("Esta prévia ainda não inclui o motor Python para distribuição.".into());
    }
    let python = std::env::var_os("PROMETEU_PYTHON")
        .map(PathBuf::from)
        .filter(|path| path.is_absolute() && path.is_file())
        .ok_or(
            "Configure PROMETEU_PYTHON com o caminho absoluto do Python com Prometeu instalado.",
        )?;
    if request.len() > MAX_REQUEST {
        return Err("Os dados da conversão são longos demais.".into());
    }
    let mut command = Command::new(&python);
    #[cfg(unix)]
    command.process_group(0);
    let mut child = command
        .args(["-I", "-m", module])
        .current_dir(python.parent().ok_or(BRIDGE_ERROR)?)
        .env_remove("PYTHONPATH")
        .env_remove("PYTHONHOME")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| BRIDGE_ERROR)?;
    // Pipes são criados acima. Fechar stdin entrega EOF ao protocolo de uma requisição.
    if child
        .stdin
        .take()
        .expect("stdin piped")
        .write_all(&request)
        .is_err()
    {
        stop_child(&mut child);
        return Err(BRIDGE_ERROR.into());
    }
    let stdout = child.stdout.take().expect("stdout piped");
    let reader = std::thread::spawn(move || {
        let mut bytes = Vec::new();
        stdout
            .take(MAX_REPLY + 1)
            .read_to_end(&mut bytes)
            .map(|_| bytes)
    });
    let started = Instant::now();
    let status = loop {
        if closing.load(Ordering::SeqCst) {
            stop_child(&mut child);
            break Err(interrupted);
        }
        match child.try_wait() {
            Ok(Some(status)) => break Ok(status),
            Ok(None) if started.elapsed() < Duration::from_secs(130) => {
                std::thread::sleep(Duration::from_millis(20));
            }
            _ => {
                stop_child(&mut child);
                break Err(timed_out);
            }
        }
    };
    let bytes = reader
        .join()
        .map_err(|_| BRIDGE_ERROR)?
        .map_err(|_| BRIDGE_ERROR)?;
    let status = status?;
    if bytes.len() as u64 > MAX_REPLY {
        return Err(BRIDGE_ERROR.into());
    }
    Ok((status, bytes))
}

fn inspect(path: PathBuf, closing: &AtomicBool) -> Result<Inspection, String> {
    let request =
        serde_json::to_vec(&serde_json::json!({ "path": path })).map_err(|_| BRIDGE_ERROR)?;
    let (status, bytes) = run_bridge(
        "prometeu.application.desktop_inspect",
        request,
        closing,
        "Inspeção interrompida ao fechar o aplicativo.",
        "A inspeção excedeu o tempo disponível ou foi interrompida.",
    )?;
    let reply: Reply = serde_json::from_slice(&bytes).map_err(|_| BRIDGE_ERROR)?;
    match (reply.ok, status.success(), reply.inspection, reply.error) {
        (true, true, Some(inspection), None) => Ok(inspection),
        (false, false, None, Some(error)) => Err(error.message),
        _ => Err(BRIDGE_ERROR.into()),
    }
}

fn convert(
    source: PathBuf,
    output: PathBuf,
    metadata: ConversionMetadata,
    closing: &AtomicBool,
) -> Result<Conversion, String> {
    let request = serde_json::to_vec(&serde_json::json!({
        "path": source,
        "output": output,
        "title": metadata.title,
        "author": (!metadata.author.trim().is_empty()).then_some(metadata.author),
        "language": metadata.language,
        "identifier": (!metadata.identifier.trim().is_empty()).then_some(metadata.identifier),
    }))
    .map_err(|_| BRIDGE_ERROR)?;
    let (status, bytes) = run_bridge(
        "prometeu.application.desktop_convert",
        request,
        closing,
        "Conversão interrompida ao fechar o aplicativo.",
        "A conversão excedeu o tempo disponível ou foi interrompida.",
    )?;
    let reply: ConversionReply = serde_json::from_slice(&bytes).map_err(|_| BRIDGE_ERROR)?;
    match (reply.ok, status.success(), reply.conversion, reply.error) {
        (true, true, Some(conversion), None) => Ok(conversion),
        (false, false, None, Some(error)) => Err(error.message),
        _ => Err(BRIDGE_ERROR.into()),
    }
}

#[tauri::command]
async fn select_and_inspect_pdf(
    app: tauri::AppHandle,
    progress: Channel<String>,
    state: State<'_, Arc<InspectionState>>,
) -> Result<Option<Inspection>, String> {
    if state.closing.load(Ordering::SeqCst)
        || state
            .busy
            .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
            .is_err()
    {
        return Err("Uma inspeção já está em andamento ou o aplicativo está encerrando.".into());
    }
    let task_state = Arc::clone(&state);
    let dialog_app = app.clone();
    let result = tauri::async_runtime::spawn_blocking(move || {
        let selected = dialog_app
            .dialog()
            .file()
            .add_filter("PDF", &["pdf"])
            .blocking_pick_file();
        if task_state.closing.load(Ordering::SeqCst) {
            return Ok(None);
        }
        match selected {
            None => Ok(None),
            Some(file) => {
                let path = file.into_path().map_err(|_| "Selecione um PDF local.")?;
                let _ = progress.send("inspecting".to_string());
                let inspection = inspect(path.clone(), &task_state.closing)?;
                *task_state.selected.lock().map_err(|_| BRIDGE_ERROR)? = Some(path);
                *task_state.output.lock().map_err(|_| BRIDGE_ERROR)? = None;
                Ok(Some(inspection))
            }
        }
    })
    .await;
    state.busy.store(false, Ordering::SeqCst);
    if state.closing.load(Ordering::SeqCst) {
        app.exit(0);
    }
    result.map_err(|_| BRIDGE_ERROR.to_string())?
}

#[tauri::command]
async fn convert_selected_pdf(
    app: tauri::AppHandle,
    metadata: ConversionMetadata,
    progress: Channel<String>,
    state: State<'_, Arc<InspectionState>>,
) -> Result<Option<Conversion>, String> {
    let source = state
        .selected
        .lock()
        .map_err(|_| BRIDGE_ERROR)?
        .clone()
        .ok_or("Selecione e inspecione um PDF antes de converter.")?;
    if state.closing.load(Ordering::SeqCst)
        || state
            .busy
            .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
            .is_err()
    {
        return Err("Outra operação já está em andamento ou o aplicativo está encerrando.".into());
    }
    let default_name = format!(
        "{}.epub",
        source
            .file_stem()
            .and_then(|name| name.to_str())
            .unwrap_or("livro")
    );
    let task_state = Arc::clone(&state);
    let dialog_app = app.clone();
    let result = tauri::async_runtime::spawn_blocking(move || {
        let selected = dialog_app
            .dialog()
            .file()
            .add_filter("EPUB", &["epub"])
            .set_file_name(default_name)
            .blocking_save_file();
        if task_state.closing.load(Ordering::SeqCst) {
            return Ok(None);
        }
        match selected {
            None => Ok(None),
            Some(file) => {
                let output = file
                    .into_path()
                    .map_err(|_| "Selecione um destino EPUB local.")?;
                if !output
                    .extension()
                    .and_then(|value| value.to_str())
                    .is_some_and(|value| value.eq_ignore_ascii_case("epub"))
                {
                    return Err("O destino deve usar a extensão .epub.".into());
                }
                let _ = progress.send("converting".to_string());
                let conversion = convert(source, output.clone(), metadata, &task_state.closing)?;
                *task_state.output.lock().map_err(|_| BRIDGE_ERROR)? = Some(output);
                Ok(Some(conversion))
            }
        }
    })
    .await;
    state.busy.store(false, Ordering::SeqCst);
    if state.closing.load(Ordering::SeqCst) {
        app.exit(0);
    }
    result.map_err(|_| BRIDGE_ERROR.to_string())?
}

#[tauri::command]
async fn reveal_epub(state: State<'_, Arc<InspectionState>>) -> Result<(), String> {
    let path = state
        .output
        .lock()
        .map_err(|_| BRIDGE_ERROR)?
        .clone()
        .filter(|path| path.is_file())
        .ok_or("O EPUB gerado não está mais disponível nesse local.")?;
    #[cfg(target_os = "macos")]
    return tauri::async_runtime::spawn_blocking(move || {
        Command::new("/usr/bin/open")
            .arg("-R")
            .arg(path)
            .status()
            .map_err(|_| "Não foi possível localizar o EPUB no Finder.")?
            .success()
            .then_some(())
            .ok_or_else(|| "Não foi possível localizar o EPUB no Finder.".into())
    })
    .await
    .map_err(|_| BRIDGE_ERROR.to_string())?;
    #[cfg(not(target_os = "macos"))]
    Err("Localizar o EPUB está disponível somente no macOS nesta prévia.".into())
}

fn main() {
    tauri::Builder::default()
        .manage(Arc::new(InspectionState::default()))
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            select_and_inspect_pdf,
            convert_selected_pdf,
            reveal_epub
        ])
        .build(tauri::generate_context!())
        .expect("Falha ao iniciar Prometeu Desktop")
        .run(|app, event| {
            let state = app.state::<Arc<InspectionState>>();
            match event {
                tauri::RunEvent::WindowEvent {
                    event: tauri::WindowEvent::CloseRequested { api, .. },
                    ..
                } if state.busy.load(Ordering::SeqCst) => {
                    state.closing.store(true, Ordering::SeqCst);
                    api.prevent_close();
                }
                tauri::RunEvent::ExitRequested { api, .. } if state.busy.load(Ordering::SeqCst) => {
                    state.closing.store(true, Ordering::SeqCst);
                    api.prevent_exit();
                }
                _ => {}
            }
        });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[cfg(unix)]
    fn termination_reaches_worker_but_not_an_unrelated_child() {
        use std::io::{BufRead, BufReader};
        // Árvore sintética de processos; comandos fixos, sem entrada externa.
        let mut parent = Command::new("/bin/sh")
            .args(["-c", "/bin/sleep 30 & echo $!; wait"])
            .process_group(0)
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let mut worker_pid = String::new();
        BufReader::new(parent.stdout.take().unwrap())
            .read_line(&mut worker_pid)
            .unwrap();
        let worker_pid: i32 = worker_pid.trim().parse().unwrap();
        let mut unrelated = Command::new("/bin/sleep").arg("30").spawn().unwrap();
        stop_child(&mut parent);
        let unrelated_alive = unrelated.try_wait().unwrap().is_none();
        unrelated.kill().unwrap();
        unrelated.wait().unwrap();
        assert!(
            unrelated_alive,
            "O processo fora do grupo deve continuar vivo"
        );
        assert!(!parent.wait().unwrap().success());
        let deadline = Instant::now() + Duration::from_secs(2);
        // Sinal 0 somente consulta o PID capturado da fixture; não envia sinal de término.
        while unsafe { libc::kill(worker_pid, 0) } == 0 && Instant::now() < deadline {
            std::thread::sleep(Duration::from_millis(20));
        }
        assert_eq!(
            unsafe { libc::kill(worker_pid, 0) },
            -1,
            "Worker ainda presente"
        );
    }

    #[test]
    #[ignore = "Requer PROMETEU_PYTHON apontando para o venv com este checkout instalado"]
    fn inspects_real_synthetic_fixture() {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../../tests/fixtures/sample.pdf")
            .canonicalize()
            .unwrap();
        let result = inspect(path, &AtomicBool::new(false)).unwrap();
        assert!(matches!(result.kind, DocumentKind::Textual));
        assert_eq!(result.page_count, 2);
        assert_eq!(result.file_name, "sample.pdf");
    }

    #[test]
    #[ignore = "Requer PROMETEU_PYTHON apontando para o venv com este checkout instalado"]
    fn converts_real_synthetic_fixture() {
        let source = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../../tests/fixtures/sample.pdf")
            .canonicalize()
            .unwrap();
        let output = std::env::temp_dir().join(format!(
            "prometeu-desktop-{}-{}.epub",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let result = convert(
            source,
            output.clone(),
            ConversionMetadata {
                title: "Título da interface".into(),
                author: "Autora fictícia".into(),
                language: "pt-BR".into(),
                identifier: "urn:prometeu:rust-test".into(),
            },
            &AtomicBool::new(false),
        )
        .unwrap();
        assert!(output.is_file());
        assert_eq!(
            PathBuf::from(result.output_path).canonicalize().unwrap(),
            output.canonicalize().unwrap()
        );
        std::fs::remove_file(output).unwrap();
    }
}
