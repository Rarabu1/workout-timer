#!/usr/bin/env python3
"""
Security Check Script for Workout Timer

This script runs security tests and audits for the workout timer application.
"""

import subprocess
import sys
import os

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"\n🔍 {description}")
    print("=" * 50)
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("Warnings/Errors:")
            print(result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running command: {e}")
        return False

def main():
    """Main security check function."""
    print("🔒 Workout Timer Security Check")
    print("=" * 50)
    
    # Check if virtual environment is activated
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Warning: Virtual environment not detected. Consider activating it first.")
        print("   Run: source venv/bin/activate")
    
    success_count = 0
    total_checks = 5
    
    # 1. Security audit on dependencies
    if run_command("python -m pip_audit --requirement requirements.txt", 
                   "Checking for security vulnerabilities in dependencies"):
        success_count += 1
        print("✅ Dependencies security check passed")
    else:
        print("❌ Dependencies security check failed")
    
    # 2. Security audit on dev dependencies
    if run_command("python -m pip_audit --requirement requirements-dev.txt", 
                   "Checking for security vulnerabilities in dev dependencies"):
        success_count += 1
        print("✅ Dev dependencies security check passed")
    else:
        print("❌ Dev dependencies security check failed")
    
    # 3. Run security tests
    if run_command("python -m pytest tests/test_security.py -v", 
                   "Running security tests"):
        success_count += 1
        print("✅ Security tests passed")
    else:
        print("❌ Security tests failed")
    
    # 4. Run app functionality tests
    if run_command("python -m pytest tests/test_app.py -v", 
                   "Running app functionality tests"):
        success_count += 1
        print("✅ App functionality tests passed")
    else:
        print("❌ App functionality tests failed")
    
    # 5. Run advanced security tests
    if run_command("python -m pytest tests/test_advanced_security.py -v", 
                   "Running advanced security tests"):
        success_count += 1
        print("✅ Advanced security tests passed")
    else:
        print("❌ Advanced security tests failed")
    
    # Summary
    print("\n" + "=" * 50)
    print(f"📊 Security Check Summary: {success_count}/{total_checks} checks passed")
    
    if success_count == total_checks:
        print("🎉 All security checks passed!")
        return 0
    else:
        print("⚠️  Some security checks failed. Review the output above.")
        print("\n💡 Recommendations:")
        print("   - Check the SECURITY_TESTING.md file for details")
        print("   - Fix failing tests before deployment")
        print("   - Run security audits regularly")
        return 1

if __name__ == "__main__":
    sys.exit(main())
