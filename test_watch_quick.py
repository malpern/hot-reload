#!/usr/bin/env python3
"""
Quick file watcher test that modifies the file immediately after watcher init
but before device access (to avoid the crash).
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

def test_file_watcher_quick():
    """Test the file watcher by modifying file immediately after init."""
    print("=== Quick File Watcher Test ===")
    
    # Create temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.kbd', delete=False) as f:
        temp_config = f.name
        f.write(create_test_config())
    
    try:
        print(f"Created test config: {temp_config}")
        
        # Start kanata with the test config
        cmd = [
            './target/release/kanata',
            '--cfg', temp_config,
            '--port', '37001',
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
        
        # Read output and modify file as soon as watcher is ready
        def read_and_modify():
            file_modified = False
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if line:
                    log_output.append(line)
                    print(f"[KANATA] {line}")
                    
                    # Modify file as soon as watcher is initialized (before device access)
                    if "File watcher initialized successfully" in line and not file_modified:
                        print("\n🔄 Watcher ready! Quickly modifying file before device access...")
                        try:
                            # Atomic write simulation
                            temp_path = f"{temp_config}.tmp"
                            with open(temp_path, 'w') as f:
                                f.write(modify_test_config())
                            os.rename(temp_path, temp_config)
                            print("✅ File modified atomically")
                            file_modified = True
                        except Exception as e:
                            print(f"❌ Error modifying file: {e}")
        
        thread = threading.Thread(target=read_and_modify)
        thread.daemon = True
        thread.start()
        
        # Let it run for a few seconds
        time.sleep(8)
        
        # Check results
        watcher_init = any("File watcher initialized successfully" in line for line in log_output)
        reload_detected = any("triggering reload" in line for line in log_output)
        file_change_detected = any("Config file changed" in line for line in log_output)
        
        print(f"\n--- Test Results ---")
        print(f"✅ Watcher initialized: {watcher_init}")
        print(f"✅ File change detected: {file_change_detected}")
        print(f"✅ Reload triggered: {reload_detected}")
        
        # Show relevant logs
        print("\n--- File Watcher Events ---")
        for line in log_output:
            if any(keyword in line.lower() for keyword in 
                  ["file watcher", "config file changed", "triggering reload", "event received"]):
                print(f"  🔍 {line}")
        
        return watcher_init and (file_change_detected or reload_detected)
        
    except Exception as e:
        print(f"Test error: {e}")
        return False
    finally:
        # Cleanup
        try:
            process.terminate()
            process.wait(timeout=3)
        except:
            try:
                process.kill()
            except:
                pass
        
        try:
            os.unlink(temp_config)
            print(f"Cleaned up: {temp_config}")
        except:
            pass

def main():
    success = test_file_watcher_quick()
    
    if success:
        print("\n🎉 SUCCESS! File watcher detected the atomic write!")
        print("The fix is working correctly.")
        return 0
    else:
        print("\n⚠️  Test inconclusive or failed.")
        print("May need to test with actual permissions.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)