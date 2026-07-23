use std::{path::PathBuf, process::{Child, Command, Stdio}, sync::Mutex};
use tauri::Manager;

struct SidecarState(Mutex<Option<Child>>);

fn spawn_sidecar() -> Result<Child, String> {
    let _ = dotenvy::from_path(PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().unwrap().join(".env"));
    let sidecar_name = if cfg!(windows) { "wiki-agent-core.exe" } else { "wiki-agent-core" };
    let bundled = std::env::current_exe().ok().and_then(|p| p.parent().map(|d| d.join(sidecar_name)));
    let mut command = if bundled.as_ref().is_some_and(|p| p.exists()) {
        Command::new(bundled.unwrap())
    } else {
        let python = std::env::var("WIKI_AGENT_PYTHON").unwrap_or_else(|_| "/Users/404name/code/temp/langgraph-graphiti-expert/.venv/bin/python".into());
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf();
        let mut cmd = Command::new(python);
        cmd.arg(root.join("python-core/run_sidecar.py")).current_dir(root.join("python-core"));
        cmd
    };
    command.args(["--port", "19829"]).stdout(Stdio::null()).stderr(Stdio::inherit()).spawn().map_err(|e| e.to_string())
}

#[tauri::command]
fn sidecar_info(state: tauri::State<SidecarState>) -> serde_json::Value {
    let running = state.0.lock().map(|guard| guard.is_some()).unwrap_or(false);
    serde_json::json!({"running": running, "apiUrl": "http://127.0.0.1:19829"})
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let child = spawn_sidecar().map_err(|e| Box::<dyn std::error::Error>::from(e))?;
            app.manage(SidecarState(Mutex::new(Some(child))));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![sidecar_info])
        .build(tauri::generate_context!())
        .expect("error while building Wiki Agent");
    app.run(|handle, event| {
        if let tauri::RunEvent::Exit = event {
            if let Some(state) = handle.try_state::<SidecarState>() {
                if let Ok(mut guard) = state.0.lock() {
                    if let Some(mut child) = guard.take() { let _ = child.kill(); }
                }
            }
        }
    });
}
