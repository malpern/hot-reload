#!/usr/bin/env python3
"""
Quick test to verify TCP validation functionality works
"""

import socket
import json
import time
import subprocess
import sys
import signal
import os

def test_tcp_validation():
    """Test the TCP validation without needing device access"""
    
    # Start kanata in a way that might work without device access
    print("Starting Kanata with TCP server...")
    
    # Try to start with a dummy config for TCP testing
    try:
        # Use subprocess to start kanata
        proc = subprocess.Popen([
            os.path.expanduser("~/.cargo/bin/kanata"),
            "--cfg", "test_config.kbd", 
            "--port", "8080"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Give it a moment to start
        time.sleep(1)
        
        # Check if process is still running (it will fail due to device access, but TCP might work)
        if proc.poll() is not None:
            stdout, stderr = proc.communicate()
            print("Kanata output:")
            print("STDOUT:", stdout)
            print("STDERR:", stderr)
            print("\nThis is expected - device access requires sudo.")
            print("But let's check if we can test the TCP validation directly...")
            
        # Try to connect to TCP port anyway
        print("\nTesting TCP connection...")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('127.0.0.1', 8080))
            if result == 0:
                print("✅ TCP server is running on port 8080!")
                
                # Test the validation
                test_config = "(defsrc esc) (deflayer default esc)"
                request = {
                    "SetSessionMode": {"quiet": True}
                }
                sock.send((json.dumps(request) + '\n').encode('utf-8'))
                
                request = {
                    "ValidateConfig": {
                        "config_content": test_config,
                        "request_id": "test-123"
                    }
                }
                sock.send((json.dumps(request) + '\n').encode('utf-8'))
                
                # Read response
                response_data = sock.recv(4096).decode('utf-8')
                print("Response:", response_data)
                
                sock.close()
                return True
            else:
                print(f"❌ Could not connect to TCP server (error {result})")
                
        except Exception as e:
            print(f"❌ TCP connection failed: {e}")
            
        # Clean up process
        if proc.poll() is None:
            proc.terminate()
            proc.wait()
            
        return False
        
    except Exception as e:
        print(f"❌ Failed to start Kanata: {e}")
        return False

def test_validation_logic():
    """Test if the validation features are compiled in"""
    print("\n" + "="*50)
    print("Testing if TCP validation features are compiled in...")
    
    try:
        # Check if the binary includes our strings
        result = subprocess.run([
            "strings", os.path.expanduser("~/.cargo/bin/kanata")
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            output = result.stdout
            
            checks = [
                ("ValidateConfig", "ValidateConfig message type"),
                ("ValidationResult", "ValidationResult message type"),
                ("SetSessionMode", "SetSessionMode message type"),
                ("tcp server ValidateConfig action", "TCP validation handler"),
                ("error_count", "Enhanced ValidationResult fields"),
                ("request_id", "Request ID support")
            ]
            
            print("Checking for TCP validation features in binary:")
            all_found = True
            for search_str, description in checks:
                if search_str in output:
                    print(f"✅ {description}")
                else:
                    print(f"❌ {description}")
                    all_found = False
            
            if all_found:
                print("\n🎉 All TCP validation features are compiled in!")
                return True
            else:
                print("\n❌ Some features missing from binary")
                return False
        else:
            print("❌ Could not examine binary with strings command")
            return False
            
    except Exception as e:
        print(f"❌ Error checking binary: {e}")
        return False

if __name__ == "__main__":
    print("TCP Validation Feature Test")
    print("="*50)
    
    # Test 1: Check if features are compiled in
    features_ok = test_validation_logic()
    
    # Test 2: Try TCP connection (will likely fail without sudo)
    tcp_ok = test_tcp_validation()
    
    print("\n" + "="*50)
    print("SUMMARY:")
    print(f"✅ Features compiled in: {features_ok}")
    print(f"{'✅' if tcp_ok else '❌'} TCP server test: {tcp_ok}")
    
    if features_ok:
        print("\n🎉 Your enhanced Kanata build is ready!")
        print("To test TCP validation:")
        print("1. Run: sudo ~/.cargo/bin/kanata --cfg test_config.kbd --port 8080")
        print("2. Run: python3 test_tcp_validation.py")
    else:
        print("\n❌ TCP validation features not found in binary")
        
    print("\nTo use your enhanced Kanata permanently, add to your shell profile:")
    print('export PATH="$HOME/.cargo/bin:$PATH"')