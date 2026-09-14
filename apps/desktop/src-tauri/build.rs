fn main() {
    tauri_build::try_build(
        tauri_build::Attributes::new()
            .app_manifest(tauri_build::AppManifest::new().commands(&["select_and_inspect_pdf"])),
    )
    .expect("Falha ao configurar o shell desktop");
}
