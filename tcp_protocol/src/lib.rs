use serde::{Deserialize, Serialize};
use std::str::FromStr;

#[derive(Debug, Serialize, Deserialize)]
pub enum ServerMessage {
    LayerChange { new: String },
    LayerNames { names: Vec<String> },
    CurrentLayerInfo { name: String, cfg_text: String },
    ConfigFileReload { new: String },
    CurrentLayerName { name: String },
    MessagePush { message: serde_json::Value },
    Error { msg: String },
    ValidationResult {
        success: bool,
        errors: Vec<ValidationError>,
        warnings: Vec<ValidationError>,
        error_count: usize,
        warning_count: usize,
        #[serde(skip_serializing_if = "Option::is_none")]
        request_id: Option<String>,
    },
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ValidationError {
    pub line: usize,
    pub message: String,
    pub severity: String,
    #[serde(default)]
    pub column: Option<usize>,
    #[serde(default)]
    pub file: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
#[serde(tag = "status")]
pub enum ServerResponse {
    Ok,
    Error { msg: String },
}

impl ServerResponse {
    pub fn as_bytes(&self) -> Vec<u8> {
        let mut msg = serde_json::to_vec(self).expect("ServerResponse should serialize");
        msg.push(b'\n');
        msg
    }
}

impl ServerMessage {
    pub fn as_bytes(&self) -> Vec<u8> {
        let mut msg = serde_json::to_vec(self).expect("ServerMessage should serialize");
        msg.push(b'\n');
        msg
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ClientMessage {
    ChangeLayer {
        new: String,
    },
    RequestLayerNames {},
    RequestCurrentLayerInfo {},
    RequestCurrentLayerName {},
    ActOnFakeKey {
        name: String,
        action: FakeKeyActionMessage,
    },
    SetMouse {
        x: u16,
        y: u16,
    },
    Reload {},
    ReloadNext {},
    ReloadPrev {},
    ReloadNum {
        index: usize,
    },
    ReloadFile {
        path: String,
    },
    ValidateConfig {
        config_content: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        request_id: Option<String>,
    },
    SetSessionMode {
        quiet: bool,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Deserialize, Serialize)]
pub enum FakeKeyActionMessage {
    Press,
    Release,
    Tap,
    Toggle,
}

impl FromStr for ClientMessage {
    type Err = serde_json::Error;

    fn from_str(s: &str) -> std::result::Result<Self, Self::Err> {
        serde_json::from_str(s)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_server_response_json_format() {
        // Test that our API contract matches expected JSON structure
        assert_eq!(
            serde_json::to_string(&ServerResponse::Ok).unwrap(),
            r#"{"status":"Ok"}"#
        );
        assert_eq!(
            serde_json::to_string(&ServerResponse::Error {
                msg: "test".to_string()
            })
            .unwrap(),
            r#"{"status":"Error","msg":"test"}"#
        );
    }

    #[test]
    fn test_as_bytes_includes_newline() {
        // Test our specific logic that adds newline termination
        let response = ServerResponse::Ok;
        let bytes = response.as_bytes();
        assert!(bytes.ends_with(b"\n"), "Response should end with newline");

        let error_response = ServerResponse::Error {
            msg: "test".to_string(),
        };
        let error_bytes = error_response.as_bytes();
        assert!(
            error_bytes.ends_with(b"\n"),
            "Error response should end with newline"
        );
    }

    #[test]
    fn test_validate_config_message_serialization() {
        // Test ValidateConfig client message serialization
        let validate_msg = ClientMessage::ValidateConfig {
            config_content: "(defsrc esc) (deflayer default esc)".to_string(),
            request_id: Some("req-456".to_string()),
        };
        
        let json = serde_json::to_string(&validate_msg).unwrap();
        assert!(json.contains("ValidateConfig"));
        assert!(json.contains("config_content"));
        
        // Test deserialization
        let deserialized: ClientMessage = serde_json::from_str(&json).unwrap();
        match deserialized {
            ClientMessage::ValidateConfig { config_content, request_id } => {
                assert_eq!(config_content, "(defsrc esc) (deflayer default esc)");
                assert_eq!(request_id, Some("req-456".to_string()));
            }
            _ => panic!("Expected ValidateConfig message"),
        }
    }

    #[test]
    fn test_validation_result_message_serialization() {
        // Test ValidationResult server message serialization with new fields
        let validation_msg = ServerMessage::ValidationResult {
            success: false,
            errors: vec![ValidationError {
                line: 42,
                message: "Test error".to_string(),
                severity: "error".to_string(),
                column: Some(15),
                file: Some("config.kbd".to_string()),
            }],
            warnings: vec![ValidationError {
                line: 10,
                message: "Test warning".to_string(),
                severity: "warning".to_string(),
                column: None,
                file: None,
            }],
            error_count: 1,
            warning_count: 1,
            request_id: Some("test-123".to_string()),
        };
        
        let json = serde_json::to_string(&validation_msg).unwrap();
        assert!(json.contains("ValidationResult"));
        assert!(json.contains("success"));
        assert!(json.contains("errors"));
        assert!(json.contains("warnings"));
        assert!(json.contains("Test error"));
        assert!(json.contains("Test warning"));
        assert!(json.contains("config.kbd"));
        
        // Test deserialization
        let deserialized: ServerMessage = serde_json::from_str(&json).unwrap();
        match deserialized {
            ServerMessage::ValidationResult { success, errors, warnings, error_count, warning_count, request_id } => {
                assert!(!success);
                assert_eq!(errors.len(), 1);
                assert_eq!(warnings.len(), 1);
                assert_eq!(error_count, 1);
                assert_eq!(warning_count, 1);
                assert_eq!(request_id, Some("test-123".to_string()));
                assert_eq!(errors[0].line, 42);
                assert_eq!(errors[0].message, "Test error");
                assert_eq!(errors[0].column, Some(15));
                assert_eq!(errors[0].file, Some("config.kbd".to_string()));
                assert_eq!(warnings[0].line, 10);
                assert_eq!(warnings[0].message, "Test warning");
                assert_eq!(warnings[0].column, None);
                assert_eq!(warnings[0].file, None);
            }
            _ => panic!("Expected ValidationResult message"),
        }
    }

    #[test]
    fn test_set_session_mode_message_serialization() {
        // Test SetSessionMode client message serialization
        let session_msg = ClientMessage::SetSessionMode { quiet: true };
        
        let json = serde_json::to_string(&session_msg).unwrap();
        assert!(json.contains("SetSessionMode"));
        assert!(json.contains("quiet"));
        assert!(json.contains("true"));
        
        // Test deserialization
        let deserialized: ClientMessage = serde_json::from_str(&json).unwrap();
        match deserialized {
            ClientMessage::SetSessionMode { quiet } => {
                assert!(quiet);
            }
            _ => panic!("Expected SetSessionMode message"),
        }
    }

    #[test]
    fn test_backward_compatibility_validation_error() {
        // Test that old ValidationError format still deserializes correctly
        let old_format_json = r#"{
            "line": 5,
            "message": "Syntax error",
            "severity": "error"
        }"#;
        
        let validation_error: ValidationError = serde_json::from_str(old_format_json).unwrap();
        assert_eq!(validation_error.line, 5);
        assert_eq!(validation_error.message, "Syntax error");
        assert_eq!(validation_error.severity, "error");
        assert_eq!(validation_error.column, None);
        assert_eq!(validation_error.file, None);
    }
}
