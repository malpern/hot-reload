#!/usr/bin/env python3
"""
Test the enhanced kanata version to see if our file watcher improvements work.
This specifically looks for our enhanced logging messages.
"""

import os
import sys
import time
import subprocess
from pathlib import Path

class EnhancedKanataTest:
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
            test_comment = f";; ENHANCED TEST #{modification_num} at {time.strftime('%H:%M:%S')}\n"
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
    
    def check_kanata_logs(self):
        """Check for our enhanced kanata logging messages."""
        try:
            # Check system logs for our specific enhanced messages
            cmd = ['log', 'show', '--predicate', 'process == "kanata"', '--last', '30s', '--style', 'compact']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                log_content = result.stdout
                
                # Look for our enhanced logging messages
                enhanced_indicators = [
                    "File watcher event received",
                    "Config file changed:",
                    "triggering reload",
                    "Directory-level change",
                    "File watcher initialized successfully"
                ]
                
                print("🔍 Checking for enhanced kanata logging...")
                found_messages = []
                for line in log_content.split('\n'):
                    for indicator in enhanced_indicators:
                        if indicator in line:
                            found_messages.append(line.strip())
                            break
                
                if found_messages:
                    print("✅ Found enhanced kanata logging:")
                    for msg in found_messages[-5:]:  # Show last 5 messages
                        print(f"  📝 {msg}")
                    return True
                else:
                    print("❌ No enhanced logging found")
                    return False
            else:
                print(f"❌ Error reading logs: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Error checking logs: {e}")
            return False
    
    def test_file_watcher_capability(self):
        """Test if our file watcher improvements work."""
        print("=== Enhanced Kanata File Watcher Test ===")
        print("Testing our improved file watcher implementation...")
        
        # Backup config
        if not self.backup_config():
            return False
        
        try:
            print("\n📊 Current kanata process:")
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'kanata' in line and '--watch' in line:
                    print(f"  {line.strip()}")
            
            # Test 1: Check for enhanced initialization messages
            print("\n--- Test 1: Check Enhanced Initialization ---")
            init_detected = self.check_kanata_logs()
            
            # Test 2: Multiple file modifications
            print("\n--- Test 2: File Modification Detection ---")
            change_detected = False
            
            for i in range(1, 3):
                print(f"\n🔄 Modification #{i}:")
                if self.modify_config_atomic(i):
                    print("⏳ Waiting 4 seconds for file watcher...")
                    time.sleep(4)
                    
                    if self.check_kanata_logs():
                        print(f"✅ Enhanced logging detected for modification #{i}")
                        change_detected = True
                        break
                    else:
                        print(f"❌ No enhanced logging for modification #{i}")
            
            # Final assessment
            print(f"\n--- Enhanced Kanata Test Results ---")
            print(f"✅ Enhanced initialization: {init_detected}")
            print(f"✅ File change detection: {change_detected}")
            
            if init_detected and change_detected:
                print("\n🎉 SUCCESS: Enhanced kanata is working!")
                print("Our file watcher improvements are active and detecting changes.")
            elif init_detected:
                print("\n⚠️ PARTIAL: Enhanced kanata running but change detection unclear")
                print("The enhanced version is installed but may need more testing.")
            else:
                print("\n❌ FAILED: Enhanced features not detected")
                print("May need to check if the enhanced version is actually running.")
            
            return init_detected and change_detected
            
        except Exception as e:
            print(f"❌ Test error: {e}")
            return False
        finally:
            self.restore_config()

def main():
    tester = EnhancedKanataTest()
    success = tester.test_file_watcher_capability()
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)