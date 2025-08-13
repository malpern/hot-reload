# TCP-Based Configuration Validation

This document describes the new TCP-based configuration validation feature added to Kanata.

## Overview

Kanata now supports real-time configuration validation through its existing TCP server, allowing external applications to validate keyboard configuration files without launching separate processes or affecting the running keyboard instance.

## Features

- **Zero overhead**: Reuses existing TCP server infrastructure
- **Real-time validation**: No process spawning, immediate response
- **Detailed errors**: Error messages with line numbers and severity levels
- **Safe operation**: Validation doesn't affect running keyboard mappings
- **Simple integration**: JSON over TCP, works with any programming language
- **Backward compatible**: Existing TCP commands continue to work unchanged

## Message Protocol

### ValidateConfig Request

Send a `ValidateConfig` message to validate a configuration:

```json
{
  "ValidateConfig": {
    "config_content": "(defsrc esc 1 2) (deflayer default esc 1 2)",
    "request_id": "optional-request-id"
  }
}
```

### ValidationResult Response

The server responds with a `ValidationResult` message:

```json
{
  "ValidationResult": {
    "success": true,
    "errors": [],
    "warnings": [],
    "error_count": 0,
    "warning_count": 0,
    "request_id": "optional-request-id"
  }
}
```

For invalid configurations:

```json
{
  "ValidationResult": {
    "success": false,
    "errors": [
      {
        "line": 3,
        "message": "Error in configuration: unexpected end of input",
        "severity": "error",
        "column": 15,
        "file": "configuration"
      }
    ],
    "warnings": [],
    "error_count": 1,
    "warning_count": 0,
    "request_id": "optional-request-id"
  }
}
```

### SetSessionMode Request (Optional)

To avoid receiving initial events, send a `SetSessionMode` message as the first message:

```json
{
  "SetSessionMode": {
    "quiet": true
  }
}
```

## Response Structure

### ValidationResult Fields
- `success`: Boolean indicating if validation passed
- `errors`: Array of error objects
- `warnings`: Array of warning objects  
- `error_count`: Number of errors (convenience field for UI)
- `warning_count`: Number of warnings (convenience field for UI)
- `request_id`: Optional string echoed from request (for correlation)

### Error/Warning Structure
Each error/warning object contains:
- `line`: Line number where the error occurred (1-based)
- `message`: Human-readable error description
- `severity`: Either "error" or "warning"
- `column`: Optional column number where the error occurred (1-based)
- `file`: Optional file name where the error occurred

## Connection Handshake

**Improved Handshake**: The TCP server now supports proper quiet mode:

1. **For validation-only clients**: Send `SetSessionMode` with `quiet: true` as the **first message** to suppress the initial `LayerChange` and other unsolicited events.
2. **For regular clients**: Don't send `SetSessionMode` or send `quiet: false` to receive layer change notifications.
3. **Passive clients**: If a client connects and doesn't send any message, no initial `LayerChange` will be sent until the first command is received.

**Protocol Details:**
- JSON format uses externally tagged enums, so responses have the message type as the top-level key
- Malformed JSON requests return a `ServerResponse` of the form `{"status":"Error","msg":"..."}`
- `ValidateConfig` always responds with a `ValidationResult` envelope (even for size limit errors)
- Maximum configuration size: 1 MB (1,048,576 bytes)

**Client Implementation Recommendation**: Parse line-by-line and filter by top-level tag as shown in the examples below.

## Usage Examples

### Command Line Testing

```bash
# Start kanata with TCP server
sudo kanata --cfg config.kbd --port 8080

# Validate config from command line (with quiet mode)
(echo '{"SetSessionMode":{"quiet":true}}'; echo '{"ValidateConfig":{"config_content":"(defsrc esc) (deflayer default esc)"}}') | nc 127.0.0.1 8080

# Or for regular clients (handle initial LayerChange)
echo '{"ValidateConfig":{"config_content":"(defsrc esc) (deflayer default esc)"}}' | nc 127.0.0.1 8080
# Note: You'll receive a LayerChange message first, then the ValidationResult
```

### Python Example

```python
import json
import socket

def validate_config(config_content, host='127.0.0.1', port=8080, quiet_mode=True):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    
    if quiet_mode:
        # Send SetSessionMode first to avoid initial LayerChange
        session_mode = {"SetSessionMode": {"quiet": True}}
        sock.send((json.dumps(session_mode) + '\n').encode('utf-8'))
    
    # Send validation request
    request = {"ValidateConfig": {"config_content": config_content}}
    sock.send((json.dumps(request) + '\n').encode('utf-8'))
    
    # Read response(s)
    responses = []
    while True:
        try:
            response_data = sock.recv(4096).decode('utf-8')
            if not response_data:
                break
            
            for line in response_data.strip().split('\n'):
                if line:
                    response = json.loads(line)
                    responses.append(response)
                    
                    # Look for ValidationResult
                    if 'ValidationResult' in response:
                        sock.close()
                        return response['ValidationResult']
                        
        except json.JSONDecodeError:
            break
    
    sock.close()
    return None

# Usage
config = "(defsrc esc 1 2) (deflayer default esc 1 2)"
result = validate_config(config)
if result:
    print(f"Valid: {result['success']}")
    if result['errors']:
        for error in result['errors']:
            print(f"Error on line {error['line']}: {error['message']}")
```

### JavaScript/Node.js Example

```javascript
const net = require('net');

function validateConfig(configContent, host = '127.0.0.1', port = 8080, quietMode = true) {
    return new Promise((resolve, reject) => {
        let buffer = '';
        
        const client = net.createConnection(port, host, () => {
            if (quietMode) {
                // Send SetSessionMode first
                const sessionMode = { SetSessionMode: { quiet: true } };
                client.write(JSON.stringify(sessionMode) + '\n');
            }
            
            // Send validation request
            const request = { ValidateConfig: { config_content: configContent } };
            client.write(JSON.stringify(request) + '\n');
        });
        
        client.on('data', (data) => {
            buffer += data.toString();
            
            // Process complete lines
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep incomplete line in buffer
            
            for (const line of lines) {
                if (line.trim()) {
                    try {
                        const response = JSON.parse(line);
                        
                        // Look for ValidationResult
                        if (response.ValidationResult) {
                            client.end();
                            resolve(response.ValidationResult);
                            return;
                        }
                    } catch (e) {
                        // Ignore JSON parse errors for partial messages
                    }
                }
            }
        });
        
        client.on('error', reject);
        client.on('end', () => reject(new Error('Connection ended without ValidationResult')));
    });
}

// Usage
(async () => {
    const config = "(defsrc esc 1 2) (deflayer default esc 1 2)";
    try {
        const result = await validateConfig(config);
        console.log(`Valid: ${result.success}`);
        if (result.errors.length > 0) {
            result.errors.forEach(error => {
                console.log(`Error on line ${error.line}: ${error.message}`);
            });
        }
    } catch (error) {
        console.error('Validation failed:', error);
    }
})();
```

## Integration with KeyPath

This feature is designed to integrate seamlessly with KeyPath and other configuration management tools:

1. **Real-time feedback**: Validate configurations as the user types
2. **Error highlighting**: Use line numbers to highlight problematic sections
3. **Safe testing**: Validate without affecting the running keyboard setup
4. **Performance**: No subprocess overhead, immediate validation results

## Error Handling

The validation system provides detailed error information by leveraging Kanata's existing configuration parser. Common error types include:

- Syntax errors (malformed S-expressions)
- Invalid key names
- Missing required sections (defsrc, deflayer)
- Configuration inconsistencies
- Platform-specific key availability issues

## Backward Compatibility

This feature is fully backward compatible:
- All existing TCP commands continue to work unchanged
- The `ValidationResult` message type was already defined in the protocol
- Only adds a new `ValidateConfig` client message type
- No changes to existing message handling

## Building and Testing

To build with TCP validation support:

```bash
cargo build --features tcp_server
```

To run tests:

```bash
cargo test --features tcp_server tcp_server::tests
cargo test -p kanata-tcp-protocol
```

## Limitations

- Validation operates at the configuration syntax level
- Does not validate platform-specific key availability at runtime
- Requires TCP server to be enabled (`--port` flag)
- Single configuration validation per request (no batch validation)