#!/usr/bin/env python3
"""
Security Alert Script

This script provides immediate notification when security issues are detected.
It can be run manually or integrated into your development workflow.
"""

import subprocess
import sys
import os
from datetime import datetime

def run_security_check():
    """Run a quick security check and return results."""
    try:
        # Run basic security tests
        result = subprocess.run(
            "python -m pytest tests/test_security.py -q",
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            return True, "All security tests passed"
        else:
            return False, result.stdout + result.stderr
            
    except Exception as e:
        return False, f"Error running security tests: {e}"

def run_dependency_check():
    """Run dependency security check."""
    try:
        result = subprocess.run(
            "python -m pip_audit --requirement requirements.txt",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Check for actual vulnerabilities (check both stdout and stderr)
        output = result.stdout + result.stderr
        if "Found" in output and "vulnerabilities" in output and "No known vulnerabilities found" not in output:
            return False, output
        elif "No known vulnerabilities found" in output:
            return True, "No dependency vulnerabilities found"
        else:
            return False, output
            
    except Exception as e:
        return False, f"Error checking dependencies: {e}"

def show_alert(message, is_error=True):
    """Show a visual alert."""
    if is_error:
        print("\n" + "🚨" * 20)
        print("🚨 SECURITY ALERT 🚨")
        print("🚨" * 20)
        print(f"🚨 {message}")
        print("🚨" * 20)
        print("\n🔧 IMMEDIATE ACTION REQUIRED:")
        print("   1. Review the security issue")
        print("   2. Fix the problem")
        print("   3. Re-run security checks")
        print("   4. Commit and push fixes")
    else:
        print("\n" + "✅" * 20)
        print("✅ SECURITY STATUS: OK ✅")
        print("✅" * 20)
        print(f"✅ {message}")

def main():
    """Main function."""
    print("🔒 Security Alert Check")
    print("=" * 40)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check dependencies
    dep_ok, dep_msg = run_dependency_check()
    if not dep_ok:
        show_alert(f"DEPENDENCY VULNERABILITIES DETECTED!\n{dep_msg}")
        return 1
    
    # Check security tests
    sec_ok, sec_msg = run_security_check()
    if not sec_ok:
        show_alert(f"SECURITY TESTS FAILED!\n{sec_msg}")
        return 1
    
    # All good
    show_alert("All security checks passed!", is_error=False)
    return 0

if __name__ == "__main__":
    sys.exit(main())
