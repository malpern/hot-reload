#!/usr/bin/env python3
"""
Live test script for kanata file watcher improvements.
This will test the actual file watching behavior with your real config.
"""

import os
import sys
import time
import subprocess
import threading
import signal
from pathlib import Path

class KanataWatchTester:
    def __init__(self):
        self.kanata_binary = "/Volumes/FlashGordon/Dropbox/code/kanata/target/release/kanata"
        self.config_path = "/Users/malpern/.config/keypath/keypath.kbd"
        self.current_kanata_pid = None
        self.test_kanata_process = None
        self.log_output = []
        self.original_config_content = None

    def find_running_kanata(self):
        """Find currently running kanata process."""
        try:
            result = subprocess.run(['pgrep', '-f', 'kanata.*--cfg'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                return [int(pid) for pid in pids if pid]
            return []
        except Exception as e:
            print(f"Error finding kanata processes: {e}")
            return []

    def stop_current_kanata(self):
        """Stop the currently running kanata."""
        pids = self.find_running_kanata()
        if pids:
            print(f"Stopping current kanata processes: {pids}")
            for pid in pids:
                try:
                    # Use sudo to stop the root process
                    subprocess.run(['sudo', 'kill', '-TERM', str(pid)], check=True)
                    time.sleep(1)
                    # Force kill if still running
                    subprocess.run(['sudo', 'kill', '-KILL', str(pid)], 
                                 check=False, capture_output=True)
                except Exception as e:
                    print(f"Error stopping kanata PID {pid}: {e}")
        else:
            print("No running kanata processes found")

    def backup_config(self):
        """Backup the original config."""
        try:
            with open(self.config_path, 'r') as f:
                self.original_config_content = f.read()
            print(f"Backed up config from {self.config_path}")
        except Exception as e:
            print(f"Error backing up config: {e}")
            return False
        return True

    def restore_config(self):
        """Restore the original config."""
        if self.original_config_content:
            try:
                with open(self.config_path, 'w') as f:
                    f.write(self.original_config_content)
                print("Restored original config")
            except Exception as e:
                print(f"Error restoring config: {e}")

    def modify_config(self, modification_type="add_mapping"):
        """Modify the config file to test file watching."""
        if not self.original_config_content:
            print("No backup found, cannot modify config safely")
            return False

        try:
            if modification_type == "add_mapping":
                # Add a test mapping: 9 -> 0
                modified = self.original_config_content.replace(
                    "(defsrc", "(defsrc\n  9"
                ).replace(
                    "(deflayer", "(deflayer base\n  0"
                )
            elif modification_type == "remove_mapping":
                # Remove the test mapping
                modified = self.original_config_content.replace(
                    "\n  9", ""
                ).replace(
                    "\n  0", ""
                )
            else:
                # Simple comment addition
                modified = f";; Test modification at {time.time()}\n{self.original_config_content}"

            # Write with atomic operation (similar to what editors do)
            temp_path = f"{self.config_path}.tmp"
            with open(temp_path, 'w') as f:
                f.write(modified)
            os.rename(temp_path, self.config_path)
            
            print(f"Modified config: {modification_type}")
            return True
        except Exception as e:
            print(f"Error modifying config: {e}")
            return False

    def start_test_kanata(self):
        """Start our test kanata with file watching."""
        cmd = [
            'sudo', self.kanata_binary,
            '--cfg', self.config_path,
            '--port', '37000',
            '--watch',
            '--debug',
            '--log-layer-changes'
        ]
        
        print(f"Starting test kanata: {' '.join(cmd)}")
        try:
            self.test_kanata_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                preexec_fn=os.setsid  # Create new process group
            )
            
            # Start log reader thread
            def read_logs():
                for line in iter(self.test_kanata_process.stdout.readline, ''):
                    line = line.strip()
                    if line:
                        self.log_output.append(line)
                        print(f"[KANATA] {line}")
            
            self.log_thread = threading.Thread(target=read_logs)
            self.log_thread.daemon = True
            self.log_thread.start()
            
            return True
        except Exception as e:
            print(f"Error starting test kanata: {e}")
            return False

    def stop_test_kanata(self):
        """Stop the test kanata process."""
        if self.test_kanata_process:
            try:
                # Kill the entire process group
                os.killpg(os.getpgid(self.test_kanata_process.pid), signal.SIGTERM)
                self.test_kanata_process.wait(timeout=5)
            except Exception as e:
                print(f"Error stopping test kanata: {e}")
                try:
                    os.killpg(os.getpgid(self.test_kanata_process.pid), signal.SIGKILL)
                except:
                    pass

    def restart_original_kanata(self):
        """Restart the original kanata service."""
        try:
            # Try to restart via launchctl if it's a service
            subprocess.run(['sudo', 'launchctl', 'kickstart', '-k', 
                          'system/local.kanata'], check=False)
            time.sleep(2)
            
            # Check if it's running
            pids = self.find_running_kanata()
            if pids:
                print(f"Original kanata restarted successfully (PID: {pids})")
            else:
                print("Warning: Could not restart original kanata automatically")
                print("You may need to restart it manually")
        except Exception as e:
            print(f"Error restarting original kanata: {e}")

    def run_test(self):
        """Run the complete file watcher test."""
        print("=== Kanata File Watcher Test ===")
        
        try:
            # Step 1: Backup config
            if not self.backup_config():
                return False

            # Step 2: Stop current kanata
            self.stop_current_kanata()
            time.sleep(2)

            # Step 3: Start test kanata
            if not self.start_test_kanata():
                return False

            # Step 4: Wait for initialization
            print("Waiting for kanata to initialize...")
            time.sleep(3)

            # Step 5: Check initialization logs
            init_success = any("File watcher initialized successfully" in line 
                             for line in self.log_output)
            if init_success:
                print("✅ File watcher initialization detected")
            else:
                print("❌ File watcher initialization not detected")

            # Step 6: Test file modification
            print("\n--- Testing file modification detection ---")
            self.modify_config("add_mapping")
            time.sleep(2)  # Wait for file watcher

            # Check for reload detection
            reload_detected = any("triggering reload" in line 
                                for line in self.log_output[-10:])  # Check recent logs
            if reload_detected:
                print("✅ File change detected and reload triggered")
            else:
                print("❌ File change not detected")

            # Step 7: Test second modification
            print("\n--- Testing second modification ---")
            self.modify_config("remove_mapping")
            time.sleep(2)

            # Check for second reload
            second_reload = any("triggering reload" in line 
                              for line in self.log_output[-5:])
            if second_reload:
                print("✅ Second file change detected")
            else:
                print("❌ Second file change not detected")

            # Step 8: Show relevant logs
            print("\n--- Relevant Log Entries ---")
            for line in self.log_output:
                if any(keyword in line.lower() for keyword in 
                      ["watch", "reload", "file", "event", "directory", "config"]):
                    print(f"  {line}")

            return init_success and reload_detected

        except KeyboardInterrupt:
            print("\nTest interrupted by user")
            return False
        except Exception as e:
            print(f"Test error: {e}")
            return False
        finally:
            # Cleanup
            print("\n--- Cleanup ---")
            self.stop_test_kanata()
            self.restore_config()
            time.sleep(1)
            self.restart_original_kanata()

def main():
    if os.geteuid() == 0:
        print("Please run this script as a regular user (it will use sudo when needed)")
        return 1

    tester = KanataWatchTester()
    success = tester.run_test()
    
    if success:
        print("\n🎉 File watcher test PASSED! The fix appears to be working.")
        return 0
    else:
        print("\n❌ File watcher test FAILED. Check the logs above for details.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)