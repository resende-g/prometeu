#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
#[cfg(unix)]
use std::os::unix::process::CommandExt;
use std::{
    io::{Read, Write},
    path::PathBuf,
    process::{Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    time::{Duration, Instant},
};
use tauri::{ipc::Channel, Manager, State};
use tauri_plugin_dialog::DialogExt;

const BRIDGE_ERROR: &str =
    "Não foi possível executar a inspeção local. Verifique a instalação do Prometeu.";
const MAX_REPLY: u64 = 64 * 1024;

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

#[derive(Default)]
struct InspectionState {
    busy: AtomicBool,
    closing: AtomicBool,
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

fn inspect(path: PathBuf, closing: &AtomicBool) -> Result<Inspection, String> {
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
    let request =
        serde_json::to_vec(&serde_json::json!({ "path": path })).map_err(|_| BRIDGE_ERROR)?;
    if request.len() > 16 * 1024 {
        return Err("O caminho do PDF é longo demais.".into());
    }
    let mut command = Command::new(&python);
    #[cfg(unix)]
    command.process_group(0);
    let mut child = command
        .args(["-I", "-m", "prometeu.application.desktop_inspect"])
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
            break Err("Inspeção interrompida ao fechar o aplicativo.");
        }
        match child.try_wait() {
            Ok(Some(status)) => break Ok(status),
            Ok(None) if started.elapsed() < Duration::from_secs(130) => {
                std::thread::sleep(Duration::from_millis(20));
            }
            _ => {
                stop_child(&mut child);
                break Err("A inspeção excedeu o tempo disponível ou foi interrompida.");
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
    let reply: Reply = serde_json::from_slice(&bytes).map_err(|_| BRIDGE_ERROR)?;
    match (reply.ok, status.success(), reply.inspection, reply.error) {
        (true, true, Some(inspection), None) => Ok(inspection),
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
                inspect(path, &task_state.closing).map(Some)
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

fn main() {
    tauri::Builder::default()
        .manage(Arc::new(InspectionState::default()))
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![select_and_inspect_pdf])
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
}
