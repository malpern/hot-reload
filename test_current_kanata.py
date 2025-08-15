#!/usr/bin/env python3
"""
Automated test to check if the current kanata service detects file changes.
This will modify your config file and check system logs for reload messages.
"""

import os
import sys
import time
import subprocess
import tempfile
from pathlib import Path

class CurrentKanataTest:
    def __init__(self):
        self.config_path = "/Users/malpern/.config/keypath/keypath.kbd"
        self.backup_content = None
        
    def backup_config(self):
        """Backup current config."""
        try:
            with open(self.config_path, 'r') as f:
                self.backup_content = f.read()
            print(f"✅ Backed up config ({len(self.backup_content)} bytes)")
            return True
        except Exception as e:
            print(f"❌ Error backing up config: {e}")
            return False
    
    def restore_config(self):
        """Restore original config."""
        if self.backup_content:
            try:
                with open(self.config_path, 'w') as f:
                    f.write(self.backup_content)
                print("✅ Restored original config")
            except Exception as e:
                print(f"❌ Error restoring config: {e}")
    
    def modify_config_atomic(self, modification_num):
        """Modify config using atomic write (like KeyPath does)."""
        try:
            # Add a test comment with timestamp
            test_comment = f";; Test modification #{modification_num} at {time.strftime('%H:%M:%S')}\n"
            modified_content = test_comment + self.backup_content
            
            # Atomic write: write to temp file then rename (simulates KeyPath behavior)
            temp_path = f"{self.config_path}.tmp{modification_num}"
            with open(temp_path, 'w') as f:
                f.write(modified_content)
            
            # The atomic rename that editors do
            os.rename(temp_path, self.config_path)
            print(f"✅ Applied atomic modification #{modification_num}")
            return True
        except Exception as e:
            print(f"❌ Error modifying config: {e}")
            return False
    
    def check_system_logs_for_reload(self, since_time):
        """Check system logs for kanata reload messages."""
        try:
            # Get logs since the specified time
            cmd = ['log', 'show', '--predicate', 'process == "kanata"', '--start', since_time, '--style', 'compact']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                log_content = result.stdout
                reload_indicators = [
                    "live_reload_requested",
                    "reloading",
                    "config file changed",
                    "file watcher",
                    "reload"
                ]
                
                found_reload = any(indicator.lower() in log_content.lower() for indicator in reload_indicators)
                if found_reload:
                    print("✅ Found reload indicators in system logs")
                    # Show relevant lines
                    for line in log_content.split('\n'):
                        if any(indicator.lower() in line.lower() for indicator in reload_indicators):
                            print(f"  📝 {line.strip()}")
                    return True
                else:
                    print("❌ No reload indicators found in system logs")
                    return False
            else:
                print(f"❌ Error reading system logs: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Error checking system logs: {e}")
            return False
    
    def monitor_kanata_process(self):
        """Monitor kanata process for any changes."""
        try:
            # Get current kanata PID and start time
            result = subprocess.run(['pgrep', '-f', 'kanata'], capture_output=True, text=True)
            if result.returncode == 0:
                pid = result.stdout.strip().split('\n')[0]
                print(f"📊 Monitoring kanata PID: {pid}")
                
                # Get process start time
                ps_result = subprocess.run(['ps', '-p', pid, '-o', 'lstart='], capture_output=True, text=True)
                if ps_result.returncode == 0:
                    start_time = ps_result.stdout.strip()
                    print(f"📊 Process start time: {start_time}")
                    return pid
            return None
        except Exception as e:
            print(f"❌ Error monitoring process: {e}")
            return None
    
    def run_test(self):
        """Run the automated file watcher test."""
        print("=== Automated Kanata File Watcher Test ===")
        print("Testing current kanata service for file change detection...")
        
        # Step 1: Backup config
        if not self.backup_config():
            return False
        
        try:
            # Step 2: Monitor kanata process
            kanata_pid = self.monitor_kanata_process()
            
            # Step 3: Record start time for log checking
            start_time = time.strftime('%Y-%m-%d %H:%M:%S')
            print(f"📅 Test start time: {start_time}")
            
            # Step 4: Wait a moment to establish baseline
            time.sleep(2)
            
            # Step 5: Test multiple modifications
            reload_detected = False
            for i in range(1, 4):
                print(f"\n--- Test Modification #{i} ---")
                
                # Modify config
                if self.modify_config_atomic(i):
                    # Wait for file watcher to process
                    print("⏳ Waiting 3 seconds for file watcher...")
                    time.sleep(3)
                    
                    # Check logs for reload activity
                    if self.check_system_logs_for_reload(start_time):
                        reload_detected = True
                        print(f"✅ Modification #{i}: Reload detected!")
                        break
                    else:
                        print(f"❌ Modification #{i}: No reload detected")
                else:
                    print(f"❌ Modification #{i}: Failed to modify file")
            
            # Step 6: Final assessment
            print(f"\n--- Final Results ---")
            if reload_detected:
                print("🎉 SUCCESS: File watcher is working!")
                print("The current kanata service detected file changes.")
            else:
                print("⚠️  INCONCLUSIVE: No clear reload detected")
                print("This might indicate the file watcher issue from the bug report.")
            
            return reload_detected
            
        except KeyboardInterrupt:
            print("\n⚠️  Test interrupted by user")
            return False
        except Exception as e:
            print(f"❌ Test error: {e}")
            return False
        finally:
            # Always restore original config
            self.restore_config()

def main():
    tester = CurrentKanataTest()
    success = tester.run_test()
    
    if success:
        print("\n✅ Test completed successfully")
        return 0
    else:
        print("\n❌ Test failed or was inconclusive")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)