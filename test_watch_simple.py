#!/usr/bin/env python3
"""
Simple file watcher test that doesn't require sudo or stopping the running kanata.
Tests the file watcher on a temporary config file.
"""

import os
import sys
import time
import subprocess
import threading
import tempfile
from pathlib import Path

def create_test_config():
    """Create a minimal test config."""
    return '''(defcfg
  process-unmapped-keys yes
)

(defsrc
  caps
)

(deflayer base
  esc
)
'''

def modify_test_config():
    """Create a modified version of the test config."""
    return '''(defcfg
  process-unmapped-keys yes
)

(defsrc
  caps 2
)

(deflayer base
  esc 3
)
'''

def test_file_watcher():
    """Test the file watcher with a temporary config."""
    print("=== Testing Kanata File Watcher (Simple Test) ===")
    
    # Create temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.kbd', delete=False) as f:
        temp_config = f.name
        f.write(create_test_config())
    
    try:
        print(f"Created test config: {temp_config}")
        
        # Start kanata with the test config (using a different port)
        cmd = [
            './target/release/kanata',
            '--cfg', temp_config,
            '--port', '37001',  # Different port to avoid conflict
            '--watch',
            '--debug',
            '--log-layer-changes'
        ]
        
        print(f"Starting kanata: {' '.join(cmd)}")
        log_output = []
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd='/Volumes/FlashGordon/Dropbox/code/kanata'
        )
        
        # Read output in background
        def read_output():
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if line:
                    log_output.append(line)
                    print(f"[KANATA] {line}")
        
        thread = threading.Thread(target=read_output)
        thread.daemon = True
        thread.start()
        
        # Wait for initialization
        print("Waiting for kanata to initialize...")
        time.sleep(4)
        
        # Check if watcher initialized
        watcher_init = any("File watcher initialized successfully" in line for line in log_output)
        if watcher_init:
            print("✅ File watcher initialized successfully")
        else:
            print("❌ File watcher initialization not detected")
        
        # Modify the config file (atomic write simulation)
        print("\nModifying config file...")
        temp_path = f"{temp_config}.tmp"
        with open(temp_path, 'w') as f:
            f.write(modify_test_config())
        os.rename(temp_path, temp_config)  # Atomic rename like editors do
        print("Config modified with atomic write (write-to-temp-then-rename)")
        
        # Wait for file watcher to detect change
        time.sleep(2)
        
        # Check for reload detection
        reload_detected = any("triggering reload" in line for line in log_output)
        if reload_detected:
            print("✅ File change detected and reload triggered")
        else:
            print("❌ File change not detected")
        
        # Show file watcher related logs
        print("\n--- File Watcher Log Entries ---")
        for line in log_output:
            if any(keyword in line.lower() for keyword in 
                  ["watch", "reload", "file", "event", "directory", "config"]):
                print(f"  {line}")
        
        return watcher_init and reload_detected
        
    except Exception as e:
        print(f"Test error: {e}")
        return False
    finally:
        # Cleanup
        try:
            process.terminate()
            process.wait(timeout=5)
        except:
            try:
                process.kill()
            except:
                pass
        
        try:
            os.unlink(temp_config)
            print(f"Cleaned up test config: {temp_config}")
        except:
            pass

def main():
    success = test_file_watcher()
    
    if success:
        print("\n🎉 File watcher test PASSED!")
        print("The fix successfully detects atomic writes!")
        return 0
    else:
        print("\n❌ File watcher test FAILED.")
        print("The file watcher may not be detecting changes properly.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)