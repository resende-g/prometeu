#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::{
    io::{Read, Write},
    path::PathBuf,
    process::{Command, Stdio},
    sync::atomic::{AtomicBool, Ordering},
    time::{Duration, Instant},
};
use tauri::{ipc::Channel, State};
use tauri_plugin_dialog::DialogExt;

const BRIDGE_ERROR: &str = "Não foi possível executar a inspeção local. Verifique a instalação do Prometeu.";
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

fn inspect(path: PathBuf) -> Result<Inspection, String> {
    // ponytail: intérprete de desenvolvimento; substituir por sidecar antes de distribuir.
    if !cfg!(debug_assertions) {
        return Err("Esta prévia ainda não inclui o motor Python para distribuição.".into());
    }
    let python = std::env::var_os("PROMETEU_PYTHON")
        .map(PathBuf::from)
        .filter(|path| path.is_absolute() && path.is_file())
        .ok_or("Configure PROMETEU_PYTHON com o caminho absoluto do Python com Prometeu instalado.")?;
    let request = serde_json::to_vec(&serde_json::json!({ "path": path }))
        .map_err(|_| BRIDGE_ERROR)?;
    if request.len() > 16 * 1024 {
        return Err("O caminho do PDF é longo demais.".into());
    }
    let mut child = Command::new(&python)
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
    if child.stdin.take().expect("stdin piped").write_all(&request).is_err() {
        let _ = child.kill();
        let _ = child.wait();
        return Err(BRIDGE_ERROR.into());
    }
    let stdout = child.stdout.take().expect("stdout piped");
    let reader = std::thread::spawn(move || {
        let mut bytes = Vec::new();
        stdout.take(MAX_REPLY + 1).read_to_end(&mut bytes).map(|_| bytes)
    });
    let started = Instant::now();
    let status = loop {
        match child.try_wait() {
            Ok(Some(status)) => break Ok(status),
            Ok(None) if started.elapsed() < Duration::from_secs(130) => {
                std::thread::sleep(Duration::from_millis(20));
            }
            _ => {
                let _ = child.kill();
                let _ = child.wait();
                break Err("A inspeção excedeu o tempo disponível ou foi interrompida.");
            }
        }
    };
    let bytes = reader.join().map_err(|_| BRIDGE_ERROR)?.map_err(|_| BRIDGE_ERROR)?;
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
    busy: State<'_, AtomicBool>,
) -> Result<Option<Inspection>, String> {
    if busy.compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst).is_err() {
        return Err("Uma inspeção já está em andamento.".into());
    }
    let result = tauri::async_runtime::spawn_blocking(move || {
        let selected = app.dialog().file().add_filter("PDF", &["pdf"]).blocking_pick_file();
        match selected {
            None => Ok(None),
            Some(file) => {
                let path = file.into_path().map_err(|_| "Selecione um PDF local.")?;
                let _ = progress.send("inspecting".to_string());
                inspect(path).map(Some)
            }
        }
    }).await;
    busy.store(false, Ordering::SeqCst);
    result.map_err(|_| BRIDGE_ERROR.to_string())?
}

fn main() {
    tauri::Builder::default()
        .manage(AtomicBool::new(false))
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![select_and_inspect_pdf])
        .run(tauri::generate_context!())
        .expect("Falha ao iniciar Prometeu Desktop");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[ignore = "Requer PROMETEU_PYTHON apontando para o venv com este checkout instalado"]
    fn inspects_real_synthetic_fixture() {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../../tests/fixtures/sample.pdf")
            .canonicalize()
            .unwrap();
        let result = inspect(path).unwrap();
        assert!(matches!(result.kind, DocumentKind::Textual));
        assert_eq!(result.page_count, 2);
        assert_eq!(result.file_name, "sample.pdf");
    }
}
