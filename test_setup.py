#!/usr/bin/env python3
"""
Test script to verify VPS Manager setup and configuration
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test that all modules can be imported"""
    print("[*] Testing imports...")
    
    try:
        from vps_manager.core import VPSManager, Domain, VERSION
        print(f"  [OK] Core module imported (Version: {VERSION})")
        
        from vps_manager.config import ConfigManager
        print("  [OK] Config module imported")
        
        from vps_manager.firewall import FirewallManager
        print("  [OK] Firewall module imported")
        
        from vps_manager.security import SecurityScanner
        print("  [OK] Security module imported")
        
        from vps_manager.alerts import AlertManager
        print("  [OK] Alerts module imported")
        
        from vps_manager.docker_manager import DockerManager
        print("  [OK] Docker manager imported")
        
        from vps_manager.version_control import VersionControl
        print("  [OK] Version control imported")
        
        try:
            from vps_manager.ui import TerminalUI
            print("  [OK] UI module imported")
        except ImportError as ui_error:
            if "curses" in str(ui_error):
                print("  [!] UI module requires 'windows-curses' on Windows")
                print("      Install with: pip install windows-curses")
            else:
                raise
        
        return True
    except Exception as e:
        print(f"  [X] Import failed: {e}")
        return False

def test_config_system():
    """Test configuration system"""
    print("\n[*] Testing configuration system...")
    
    try:
        from vps_manager.config import ConfigManager, AppConfig
        
        config_mgr = ConfigManager()
        print(f"  [OK] ConfigManager initialized")
        print(f"  [*] First run: {config_mgr.is_first_run()}")
        print(f"  [*] Alerts enabled: {config_mgr.config.alerts.enabled}")
        print(f"  [*] Firewall enabled: {config_mgr.config.firewall.enabled}")
        print(f"  [*] Security enabled: {config_mgr.config.security.enabled}")
        print(f"  [*] Docker enabled: {config_mgr.config.docker.enabled}")
        print(f"  [*] Version Control enabled: {config_mgr.config.version_control.enabled}")
        
        return True
    except Exception as e:
        print(f"  [X] Config test failed: {e}")
        return False

def test_manager_initialization():
    """Test VPS Manager initialization"""
    print("\n[*] Testing VPS Manager initialization...")
    
    try:
        from vps_manager.core import VPSManager
        
        manager = VPSManager()
        print(f"  [OK] VPSManager initialized")
        print(f"  [*] Domains loaded: {len(manager.domains)}")
        print(f"  [*] Config manager: {manager.config_manager is not None}")
        print(f"  [*] Is first run: {manager.is_first_run()}")
        
        # Test lazy loading
        print(f"  [*] Firewall available: {manager.firewall is not None}")
        print(f"  [*] Security available: {manager.security is not None}")
        print(f"  [*] Alerts available: {manager.alerts is not None}")
        print(f"  [*] Docker available: {manager.docker is not None}")
        print(f"  [*] VCS available: {manager.vcs is not None}")
        
        return True
    except Exception as e:
        print(f"  [X] Manager initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_no_emojis():
    """Test that no emojis are present in UI files"""
    print("\n[*] Testing for emoji removal...")
    
    files_to_check = [
        'src/vps_manager/ui.py',
        'src/vps_manager/main.py',
        'src/vps_manager/security.py',
        'src/vps_manager/version_control.py'
    ]
    
    # Common emojis to check for
    emoji_patterns = ['✓', '✗', '⚠', '→', '•', '📊', '💾', '📜', '🔍', '↩️', '🔀', '🏷️', '📈', '⚡']
    
    all_clean = True
    for file_path in files_to_check:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                found_emojis = [emoji for emoji in emoji_patterns if emoji in content]
                
                if found_emojis:
                    print(f"  [!] Found emojis in {file_path}: {found_emojis}")
                    all_clean = False
                else:
                    print(f"  [OK] {file_path} is clean")
    
    return all_clean

def main():
    """Run all tests"""
    print("=" * 60)
    print("VPS Manager Setup Test Suite")
    print("=" * 60)
    
    results = []
    
    results.append(("Import Test", test_imports()))
    results.append(("Configuration Test", test_config_system()))
    results.append(("Manager Initialization", test_manager_initialization()))
    results.append(("Emoji Removal Test", test_no_emojis()))
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "[OK]" if passed else "[FAILED]"
        print(f"{status} {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("[OK] All tests passed!")
        print("\nYou can now run the application with:")
        print("  python -m vps_manager.main")
        print("\nOr install it with:")
        print("  pip install -e .")
        return 0
    else:
        print("[X] Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
