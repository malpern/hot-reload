#!/usr/bin/env python3
"""
Quick test for enhanced TCP validation
"""
import socket
import json

def test_tcp_validation():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        sock.connect(('127.0.0.1', 8080))
        
        # Send quiet mode first
        quiet_request = {"SetSessionMode": {"quiet": True}}
        sock.send((json.dumps(quiet_request) + '\n').encode('utf-8'))
        
        # Test invalid config
        invalid_config = """(defsrc esc 1 2 3

(deflayer default
  esc 1 2 3"""
        
        request = {
            "ValidateConfig": {
                "config_content": invalid_config,
                "request_id": "test-123"
            }
        }
        sock.send((json.dumps(request) + '\n').encode('utf-8'))
        
        # Read response
        response_data = sock.recv(4096).decode('utf-8')
        response = json.loads(response_data.strip())
        
        print("Enhanced validation response:")
        print(json.dumps(response, indent=2))
        
        if 'ValidationResult' in response:
            result = response['ValidationResult']
            print(f"\nSummary:")
            print(f"  Success: {result['success']}")
            print(f"  Errors: {result['error_count']}")
            print(f"  Warnings: {result['warning_count']}")
            
            for error in result['errors']:
                print(f"\n  Error at line {error['line']}:")
                print(f"    Category: {error.get('category', 'unknown')}")
                print(f"    Message: {error['message']}")
                if error.get('column'):
                    print(f"    Column: {error['column']}")
                if error.get('help_text'):
                    print(f"    Help: {error['help_text']}")
                    
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    test_tcp_validation()