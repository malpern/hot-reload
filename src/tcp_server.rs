use crate::Kanata;
use crate::oskbd::*;

#[cfg(feature = "tcp_server")]
use kanata_tcp_protocol::*;
use parking_lot::Mutex;
use std::net::SocketAddr;
use std::sync::Arc;
use std::sync::mpsc::SyncSender as Sender;

#[cfg(feature = "tcp_server")]
type HashMap<K, V> = rustc_hash::FxHashMap<K, V>;
#[cfg(feature = "tcp_server")]
use kanata_parser::cfg::SimpleSExpr;
#[cfg(feature = "tcp_server")]
use std::io::Write;
#[cfg(feature = "tcp_server")]
use std::net::{TcpListener, TcpStream};

#[cfg(feature = "tcp_server")]
pub type Connections = Arc<Mutex<HashMap<String, TcpStream>>>;

#[cfg(not(feature = "tcp_server"))]
pub type Connections = ();

#[cfg(feature = "tcp_server")]
use kanata_parser::custom_action::FakeKeyAction;
#[cfg(feature = "tcp_server")]
use kanata_parser::cfg::{self, DiagnosticSeverity};

#[cfg(feature = "tcp_server")]
const MAX_VALIDATION_CONFIG_BYTES: usize = 1_000_000; // 1 MiB, adjust as needed

#[cfg(feature = "tcp_server")]
fn validate_config_content(config_content: &str, request_id: Option<String>) -> ServerMessage {
    let (errors, warnings) = cfg::validate_config_str(config_content);
    
    let convert_diagnostic = |d: cfg::Diagnostic| ValidationError {
        line: d.line,
        message: d.message,
        severity: match d.severity {
            DiagnosticSeverity::Error => "error".to_string(),
            DiagnosticSeverity::Warning => "warning".to_string(),
        },
        column: d.column,
        file: d.file,
        category: Some(match d.category {
            cfg::ErrorCategory::Syntax => "syntax".to_string(),
            cfg::ErrorCategory::Semantic => "semantic".to_string(),
            cfg::ErrorCategory::Include => "include".to_string(),
            cfg::ErrorCategory::Platform => "platform".to_string(),
        }),
        help_text: d.help_text,
    };
    
    let converted_errors: Vec<ValidationError> = errors.into_iter().map(convert_diagnostic).collect();
    let converted_warnings: Vec<ValidationError> = warnings.into_iter().map(convert_diagnostic).collect();
    
    let error_count = converted_errors.len();
    let warning_count = converted_warnings.len();
    let success = error_count == 0;
    
    ServerMessage::ValidationResult {
        success,
        errors: converted_errors,
        warnings: converted_warnings,
        error_count,
        warning_count,
        request_id,
    }
}

#[cfg(feature = "tcp_server")]
fn send_message(
    stream: &mut TcpStream,
    message: ServerMessage,
    connections: &Connections,
    addr: &str,
) -> bool {
    if let Err(write_err) = stream.write_all(&message.as_bytes()) {
        log::error!("stream write error: {write_err}");
        connections.lock().remove(addr);
        return false;
    }
    true
}

#[cfg(feature = "tcp_server")]
fn send_response(
    stream: &mut TcpStream,
    response: ServerResponse,
    connections: &Connections,
    addr: &str,
) -> bool {
    if let Err(write_err) = stream.write_all(&response.as_bytes()) {
        log::error!("stream write error: {write_err}");
        connections.lock().remove(addr);
        return false;
    }
    true
}

#[cfg(feature = "tcp_server")]
fn to_action(val: FakeKeyActionMessage) -> FakeKeyAction {
    match val {
        FakeKeyActionMessage::Press => FakeKeyAction::Press,
        FakeKeyActionMessage::Release => FakeKeyAction::Release,
        FakeKeyActionMessage::Tap => FakeKeyAction::Tap,
        FakeKeyActionMessage::Toggle => FakeKeyAction::Toggle,
    }
}

#[cfg(feature = "tcp_server")]
pub struct TcpServer {
    pub address: SocketAddr,
    pub connections: Connections,
    pub wakeup_channel: Sender<KeyEvent>,
}

#[cfg(not(feature = "tcp_server"))]
pub struct TcpServer {
    pub connections: Connections,
}

impl TcpServer {
    #[cfg(feature = "tcp_server")]
    pub fn new(address: SocketAddr, wakeup_channel: Sender<KeyEvent>) -> Self {
        Self {
            address,
            connections: Arc::new(Mutex::new(HashMap::default())),
            wakeup_channel,
        }
    }

    #[cfg(not(feature = "tcp_server"))]
    pub fn new(_address: SocketAddr, _wakeup_channel: Sender<KeyEvent>) -> Self {
        Self { connections: () }
    }

    #[cfg(feature = "tcp_server")]
    pub fn start(&mut self, kanata: Arc<Mutex<Kanata>>) {
        use kanata_parser::cfg::FAKE_KEY_ROW;

        use crate::kanata::handle_fakekey_action;

        let listener = TcpListener::bind(self.address).expect("TCP server starts");

        let connections = self.connections.clone();
        let wakeup_channel = self.wakeup_channel.clone();

        std::thread::spawn(move || {
            for stream in listener.incoming() {
                match stream {
                    Ok(stream) => {
                        let addr = stream
                            .peer_addr()
                            .expect("incoming conn has known address")
                            .to_string();

                        log::info!("new client connection: {addr}");

                        connections.lock().insert(
                            addr.clone(),
                            stream.try_clone().expect("stream is clonable"),
                        );

                        let reader = serde_json::Deserializer::from_reader(
                            stream.try_clone().expect("stream is clonable"),
                        )
                        .into_iter::<ClientMessage>();

                        log::info!("listening for incoming messages {addr}");

                        let connections = connections.clone();
                        let kanata = kanata.clone();
                        let wakeup_channel = wakeup_channel.clone();
                        std::thread::spawn(move || {
                            let mut stream = stream.try_clone().expect("stream is clonable");
                            let mut quiet = false;
                            let mut sent_initial_layer_change = false;
                            for v in reader {
                                match v {
                                    Ok(event) => {
                                        log::debug!("tcp server received command: {:?}", event);
                                        
                                        // Handle SetSessionMode first to determine quiet state
                                        if let ClientMessage::SetSessionMode { quiet: q } = &event {
                                            log::info!("tcp server SetSessionMode action: quiet={q}");
                                            quiet = *q;
                                            if !*q && !sent_initial_layer_change {
                                                // Client wants layer changes, send initial one
                                                let k = kanata.lock();
                                                if let Err(e) = stream.write_all(
                                                    &ServerMessage::LayerChange {
                                                        new: k.layer_info[k.layout.b().current_layer()].name.clone(),
                                                    }
                                                    .as_bytes(),
                                                ) {
                                                    log::warn!("failed to write initial LayerChange: {e:?}");
                                                    connections.lock().remove(&addr);
                                                    break;
                                                }
                                                sent_initial_layer_change = true;
                                            }
                                            continue; // SetSessionMode doesn't need further processing
                                        }
                                        
                                        // Send initial LayerChange for non-quiet clients on first non-SetSessionMode message
                                        if !quiet && !sent_initial_layer_change {
                                            let k = kanata.lock();
                                            log::info!("sending initial LayerChange event for non-quiet client");
                                            if let Err(e) = stream.write_all(
                                                &ServerMessage::LayerChange {
                                                    new: k.layer_info[k.layout.b().current_layer()].name.clone(),
                                                }
                                                .as_bytes(),
                                            ) {
                                                log::warn!("failed to write initial LayerChange: {e:?}");
                                                connections.lock().remove(&addr);
                                                break;
                                            }
                                            sent_initial_layer_change = true;
                                        }
                                        
                                        match event {
                                            ClientMessage::ChangeLayer { new } => {
                                                kanata.lock().change_layer(new);
                                            }
                                            ClientMessage::RequestLayerNames {} => {
                                                let msg = ServerMessage::LayerNames {
                                                    names: kanata
                                                        .lock()
                                                        .layer_info
                                                        .iter()
                                                        .map(|info| info.name.clone())
                                                        .collect::<Vec<_>>(),
                                                };
                                                match stream.write_all(&msg.as_bytes()) {
                                                    Ok(_) => {}
                                                    Err(err) => log::error!(
                                                        "server could not send response: {err}"
                                                    ),
                                                }
                                            }
                                            ClientMessage::ActOnFakeKey { name, action } => {
                                                let mut k = kanata.lock();
                                                let index = match k.virtual_keys.get(&name) {
                                                    Some(index) => Some(*index as u16),
                                                    None => {
                                                        if let Err(e) = stream.write_all(
                                                            &ServerMessage::Error {
                                                                msg: format!(
                                                                "unknown virtual/fake key: {name}"
                                                            ),
                                                            }
                                                            .as_bytes(),
                                                        ) {
                                                            log::error!("stream write error: {e}");
                                                            connections.lock().remove(&addr);
                                                            break;
                                                        }
                                                        continue;
                                                    }
                                                };
                                                if let Some(index) = index {
                                                    log::info!(
                                                        "tcp server fake-key action: {name},{action:?}"
                                                    );
                                                    handle_fakekey_action(
                                                        to_action(action),
                                                        k.layout.bm(),
                                                        FAKE_KEY_ROW,
                                                        index,
                                                    );
                                                }
                                                drop(k);
                                            }
                                            ClientMessage::SetMouse { x, y } => {
                                                log::info!(
                                                    "tcp server SetMouse action: x {x} y {y}"
                                                );
                                                match kanata.lock().kbd_out.set_mouse(x, y) {
                                                    Ok(_) => {
                                                        log::info!(
                                                            "sucessfully did set mouse position to: x {x} y {y}"
                                                        );
                                                        // Optionally send a success message to the
                                                        // client
                                                    }
                                                    Err(e) => {
                                                        log::error!(
                                                            "Failed to set mouse position: {}",
                                                            e
                                                        );
                                                        // Implement any error handling logic here,
                                                        // such as sending an error response to
                                                        // the client
                                                    }
                                                }
                                            }
                                            ClientMessage::RequestCurrentLayerInfo {} => {
                                                let mut k = kanata.lock();
                                                let cur_layer = k.layout.bm().current_layer();
                                                let msg = ServerMessage::CurrentLayerInfo {
                                                    name: k.layer_info[cur_layer].name.clone(),
                                                    cfg_text: k.layer_info[cur_layer]
                                                        .cfg_text
                                                        .clone(),
                                                };
                                                drop(k);
                                                match stream.write_all(&msg.as_bytes()) {
                                                    Ok(_) => {}
                                                    Err(err) => log::error!(
                                                        "Error writing response to RequestCurrentLayerInfo: {err}"
                                                    ),
                                                }
                                            }
                                            ClientMessage::RequestCurrentLayerName {} => {
                                                let mut k = kanata.lock();
                                                let cur_layer = k.layout.bm().current_layer();
                                                let msg = ServerMessage::CurrentLayerName {
                                                    name: k.layer_info[cur_layer].name.clone(),
                                                };
                                                drop(k);
                                                match stream.write_all(&msg.as_bytes()) {
                                                    Ok(_) => {}
                                                    Err(err) => log::error!(
                                                        "Error writing response to RequestCurrentLayerName: {err}"
                                                    ),
                                                }
                                            }
                                            ClientMessage::SetSessionMode { .. } => {
                                                // SetSessionMode is handled at the top of the loop
                                                // This arm is just to satisfy the exhaustive match
                                            }
                                            ClientMessage::ValidateConfig { config_content, request_id } => {
                                                log::info!("tcp server ValidateConfig action");
                                                
                                                if config_content.len() > MAX_VALIDATION_CONFIG_BYTES {
                                                    let msg = ServerMessage::ValidationResult {
                                                        success: false,
                                                        errors: vec![ValidationError {
                                                            line: 0,
                                                            message: format!(
                                                                "config_content too large: {} bytes (max {})",
                                                                config_content.len(),
                                                                MAX_VALIDATION_CONFIG_BYTES
                                                            ),
                                                            severity: "error".to_string(),
                                                            column: None,
                                                            file: Some("configuration".to_string()),
                                                            category: Some("semantic".to_string()),
                                                            help_text: Some("Reduce configuration size or split into multiple files".to_string()),
                                                        }],
                                                        warnings: vec![],
                                                        error_count: 1,
                                                        warning_count: 0,
                                                        request_id,
                                                    };
                                                    if !send_message(&mut stream, msg, &connections, &addr) {
                                                        break;
                                                    }
                                                    continue;
                                                }
                                                
                                                let msg = validate_config_content(&config_content, request_id);
                                                if !send_message(&mut stream, msg, &connections, &addr) {
                                                    break;
                                                }
                                            }
                                            // Handle reload commands with unified response protocol
                                            reload_cmd @ (ClientMessage::Reload {}
                                            | ClientMessage::ReloadNext {}
                                            | ClientMessage::ReloadPrev {}
                                            | ClientMessage::ReloadNum { .. }
                                            | ClientMessage::ReloadFile { .. }) => {
                                                // Log specific action type
                                                match &reload_cmd {
                                                    ClientMessage::Reload {} => {
                                                        log::info!("tcp server Reload action")
                                                    }
                                                    ClientMessage::ReloadNext {} => {
                                                        log::info!("tcp server ReloadNext action")
                                                    }
                                                    ClientMessage::ReloadPrev {} => {
                                                        log::info!("tcp server ReloadPrev action")
                                                    }
                                                    ClientMessage::ReloadNum { index } => {
                                                        log::info!(
                                                            "tcp server ReloadNum action: index {index}"
                                                        )
                                                    }
                                                    ClientMessage::ReloadFile { path } => {
                                                        log::info!(
                                                            "tcp server ReloadFile action: path {path}"
                                                        )
                                                    }
                                                    _ => unreachable!(),
                                                }

                                                let response = match kanata
                                                    .lock()
                                                    .handle_client_command(reload_cmd)
                                                {
                                                    Ok(_) => ServerResponse::Ok,
                                                    Err(e) => ServerResponse::Error {
                                                        msg: format!("{e}"),
                                                    },
                                                };
                                                if !send_response(
                                                    &mut stream,
                                                    response,
                                                    &connections,
                                                    &addr,
                                                ) {
                                                    break;
                                                }
                                            }
                                        }
                                        use kanata_parser::keys::*;
                                        wakeup_channel
                                            .send(KeyEvent {
                                                code: OsCode::KEY_RESERVED,
                                                value: KeyValue::WakeUp,
                                            })
                                            .expect("write key event");
                                    }
                                    Err(e) => {
                                        log::warn!(
                                            "client sent an invalid message, disconnecting them. Err: {e:?}"
                                        );
                                        // Send proper error response for malformed JSON
                                        let response = ServerResponse::Error {
                                            msg: format!("Failed to deserialize command: {e}"),
                                        };
                                        let _ = stream.write_all(&response.as_bytes());
                                        connections.lock().remove(&addr);
                                        break;
                                    }
                                }
                            }
                            
                            // Normal disconnect / EOF: clean up connection entry.
                            log::info!("client {addr} disconnected");
                            connections.lock().remove(&addr);
                        });
                    }
                    Err(_) => log::error!("not able to accept client connection"),
                }
            }
        });
    }

    #[cfg(not(feature = "tcp_server"))]
    pub fn start(&mut self, _kanata: Arc<Mutex<Kanata>>) {}
}

#[cfg(feature = "tcp_server")]
pub fn simple_sexpr_to_json_array(exprs: &[SimpleSExpr]) -> serde_json::Value {
    let mut result = Vec::new();

    for expr in exprs.iter() {
        match expr {
            SimpleSExpr::Atom(s) => result.push(serde_json::Value::String(s.clone())),
            SimpleSExpr::List(list) => result.push(simple_sexpr_to_json_array(list)),
        }
    }

    serde_json::Value::Array(result)
}

#[cfg(all(test, feature = "tcp_server"))]
mod tests {
    use super::*;

    #[test]
    fn test_validate_config_content_valid() {
        let valid_config = r#"
(defsrc
  esc  1    2    3    4
)

(deflayer default
  esc  1    2    3    4
)
"#;
        
        match validate_config_content(valid_config, None) {
            ServerMessage::ValidationResult { success, errors, warnings, error_count, warning_count, request_id } => {
                assert!(success, "Valid config should be successful");
                assert!(errors.is_empty(), "Valid config should have no errors");
                assert!(warnings.is_empty(), "Valid config should have no warnings");
                assert_eq!(error_count, 0, "Error count should be zero");
                assert_eq!(warning_count, 0, "Warning count should be zero");
                assert_eq!(request_id, None, "Request ID should be None when not provided");
            }
            other => panic!("Expected ValidationResult, got {:?}", other),
        }
    }

    #[test]
    fn test_validate_config_content_invalid() {
        let invalid_config = r#"
(defsrc
  esc  1    2    3    4
  
(deflayer default
  esc  1    2    3    4
"#;
        
        match validate_config_content(invalid_config, Some("req-1".to_string())) {
            ServerMessage::ValidationResult { success, errors, error_count, warning_count, request_id, .. } => {
                assert!(!success, "Invalid config should fail validation");
                assert!(!errors.is_empty(), "Invalid config should have errors");
                assert_eq!(error_count, errors.len(), "Error count should match errors length");
                assert_eq!(warning_count, 0, "Warning count should be zero for this test");
                assert_eq!(request_id, Some("req-1".to_string()), "Request ID should be echoed back");
                
                let error = &errors[0];
                assert_eq!(error.severity, "error");
                assert!(!error.message.is_empty());
                assert!(error.line > 0, "Error should have a valid line number");
                assert!(error.file.is_some(), "Error should include file information");
            }
            other => panic!("Expected ValidationResult, got {:?}", other),
        }
    }

    #[test]
    fn test_validate_config_content_empty() {
        let empty_config = "";
        
        match validate_config_content(empty_config, None) {
            ServerMessage::ValidationResult { success, errors, error_count, .. } => {
                assert!(!success, "Empty config should fail validation");
                assert!(!errors.is_empty(), "Empty config should have errors");
                assert_eq!(error_count, errors.len(), "Error count should match errors length");
                
                let error = &errors[0];
                assert_eq!(error.severity, "error");
                assert!(error.line > 0, "Error should have a valid line number");
            }
            other => panic!("Expected ValidationResult, got {:?}", other),
        }
    }

    #[test]
    fn test_validate_config_content_enhanced_error_info() {
        let invalid_config = "(defsrc esc) (deflayer"; // Incomplete config
        
        match validate_config_content(invalid_config, None) {
            ServerMessage::ValidationResult { success, errors, error_count, warning_count, .. } => {
                assert!(!success);
                assert!(!errors.is_empty());
                assert_eq!(error_count, errors.len());
                assert_eq!(warning_count, 0);
                
                let error = &errors[0];
                assert_eq!(error.severity, "error");
                assert!(error.line >= 1);
                assert!(error.file.is_some());
                assert!(!error.message.is_empty());
            }
            other => panic!("Expected ValidationResult, got {:?}", other),
        }
    }

    #[test]
    fn test_validate_config_content_size_limit() {
        // Test the size limit scenario
        let _large_config = "a".repeat(MAX_VALIDATION_CONFIG_BYTES + 1);
        
        // This would normally be tested via the TCP handler, but we can test the validation logic
        // The size check happens in the TCP handler, not in validate_config_content itself
        // So we'll just verify that our function works with reasonable-sized invalid content
        let invalid_config = "(".repeat(1000); // Invalid but under size limit
        
        match validate_config_content(&invalid_config, Some("size-test".to_string())) {
            ServerMessage::ValidationResult { success, errors, request_id, .. } => {
                assert!(!success, "Invalid config should fail");
                assert!(!errors.is_empty(), "Should have parsing errors");
                assert_eq!(request_id, Some("size-test".to_string()));
            }
            other => panic!("Expected ValidationResult, got {:?}", other),
        }
    }
}
