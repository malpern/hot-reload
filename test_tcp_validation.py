#!/usr/bin/env python3
"""
Simple test script to verify TCP-based configuration validation functionality.
"""

import json
import socket

def read_lines(sock):
    """Yield complete JSON objects parsed from newline-delimited stream."""
    buffer = ""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            # Connection closed
            if buffer.strip():
                # Try to parse any trailing data (best effort)
                try:
                    yield json.loads(buffer)
                except Exception:
                    pass
            return
        buffer += chunk.decode("utf-8")
        lines = buffer.split("\n")
        buffer = lines.pop()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # Ignore partial/invalid lines; continue accumulating
                continue

def send(sock, obj):
    sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))

def validate_once(config_content, host="127.0.0.1", port=8080, quiet_mode=True):
    """Send one ValidateConfig and return the ValidationResult payload."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    if quiet_mode:
        # Send SetSessionMode first to suppress initial LayerChange
        send(sock, {"SetSessionMode": {"quiet": True}})

    send(sock, {"ValidateConfig": {"config_content": config_content, "request_id": "test-validation"}})

    result = None
    for obj in read_lines(sock):
        # In quiet mode, should only receive ValidationResult
        # In non-quiet mode, may receive LayerChange first, then ValidationResult
        if "ValidationResult" in obj:
            result = obj["ValidationResult"]
            break

    sock.close()
    return result

def test_validation(config_content, expected_success=True):
    """Test configuration validation via TCP."""
    try:
        result = validate_once(config_content)
        print(f"Request (truncated): {config_content[:50]}...")
        print("Response ValidationResult:")
        print(json.dumps(result, indent=2))
        print(f"Expected success: {expected_success}, Actual: {result.get('success', False)}")
        print(f"Error count: {result.get('error_count', 0)}, Warning count: {result.get('warning_count', 0)}")
        if result.get('request_id'):
            print(f"Request ID: {result.get('request_id')}")
        print("-" * 50)
        return result
    except Exception as e:
        print(f"Error testing validation: {e}")
        return None

def main():
    """Run validation tests."""
    print("Testing TCP Configuration Validation")
    print("=" * 50)
    
    # Test 1: Valid simple configuration
    valid_config = """
(defsrc
  esc  1    2    3    4    5    6    7    8    9    0    -    =    bspc
  tab  q    w    e    r    t    y    u    i    o    p    [    ]    \\
  caps a    s    d    f    g    h    j    k    l    ;    '    ret
  lsft z    x    c    v    b    n    m    ,    .    /    rsft
  lctl lmet lalt           spc            ralt rmet cmp  rctl
)

(deflayer default
  esc  1    2    3    4    5    6    7    8    9    0    -    =    bspc
  tab  q    w    e    r    t    y    u    i    o    p    [    ]    \\
  caps a    s    d    f    g    h    j    k    l    ;    '    ret
  lsft z    x    c    v    b    n    m    ,    .    /    rsft
  lctl lmet lalt           spc            ralt rmet cmp  rctl
)
"""
    test_validation(valid_config, expected_success=True)
    
    # Test 2: Invalid configuration (syntax error)
    invalid_config = """
(defsrc
  esc  1    2    3    4
  
(deflayer default
  esc  1    2    3    4
"""
    test_validation(invalid_config, expected_success=False)
    
    # Test 3: Invalid configuration (missing deflayer)
    missing_layer_config = """
(defsrc
  esc  1    2    3    4    5
)
"""
    test_validation(missing_layer_config, expected_success=False)

if __name__ == "__main__":
    print("NOTE: This test requires kanata to be running with TCP server enabled on port 8080")
    print("Run: sudo ./target/debug/kanata --cfg cfg_samples/minimal.kbd --port 8080")
    input("Press Enter when kanata TCP server is running on 127.0.0.1:8080...")
    main()