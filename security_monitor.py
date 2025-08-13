#!/usr/bin/env python3
"""
Security Monitor for Workout Timer

This script provides detailed security monitoring and reporting.
It can be run manually or integrated into CI/CD pipelines.
"""

import subprocess
import sys
import json
import os
from datetime import datetime
from pathlib import Path

class SecurityMonitor:
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "PASS",
            "checks": {},
            "warnings": [],
            "errors": [],
            "recommendations": []
        }
    
    def run_command(self, command, description, check_name):
        """Run a command and capture results."""
        print(f"\n🔍 {description}")
        print("=" * 60)
        
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            success = result.returncode == 0
            output = result.stdout
            errors = result.stderr
            
            self.results["checks"][check_name] = {
                "status": "PASS" if success else "FAIL",
                "command": command,
                "output": output,
                "errors": errors,
                "return_code": result.returncode
            }
            
            if success:
                print("✅ PASSED")
                print(output)
            else:
                print("❌ FAILED")
                print(f"Return code: {result.returncode}")
                print(output)
                if errors:
                    print("Errors:")
                    print(errors)
                self.results["overall_status"] = "FAIL"
                self.results["errors"].append(f"{check_name}: {description}")
            
            if errors and "warning" in errors.lower():
                self.results["warnings"].append(f"{check_name}: {errors}")
            
            return success
            
        except subprocess.TimeoutExpired:
            print("⏰ TIMEOUT")
            self.results["checks"][check_name] = {
                "status": "TIMEOUT",
                "command": command,
                "output": "",
                "errors": "Command timed out after 5 minutes",
                "return_code": -1
            }
            self.results["overall_status"] = "FAIL"
            self.results["errors"].append(f"{check_name}: Command timed out")
            return False
            
        except Exception as e:
            print(f"💥 ERROR: {e}")
            self.results["checks"][check_name] = {
                "status": "ERROR",
                "command": command,
                "output": "",
                "errors": str(e),
                "return_code": -1
            }
            self.results["overall_status"] = "FAIL"
            self.results["errors"].append(f"{check_name}: {str(e)}")
            return False
    
    def run_security_audit(self):
        """Run security audit on dependencies."""
        return self.run_command(
            "python -m pip_audit --requirement requirements.txt --format json",
            "Security Audit - Production Dependencies",
            "dependency_audit"
        )
    
    def run_dev_security_audit(self):
        """Run security audit on development dependencies."""
        return self.run_command(
            "python -m pip_audit --requirement requirements-dev.txt --format json",
            "Security Audit - Development Dependencies",
            "dev_dependency_audit"
        )
    
    def run_basic_security_tests(self):
        """Run basic security tests."""
        return self.run_command(
            "python -m pytest tests/test_security.py -v --tb=short",
            "Basic Security Tests",
            "basic_security_tests"
        )
    
    def run_advanced_security_tests(self):
        """Run advanced security tests."""
        return self.run_command(
            "python -m pytest tests/test_advanced_security.py -v --tb=short",
            "Advanced Security Tests",
            "advanced_security_tests"
        )
    
    def run_app_tests(self):
        """Run app functionality tests."""
        return self.run_command(
            "python -m pytest tests/test_app.py -v --tb=short",
            "App Functionality Tests",
            "app_tests"
        )
    
    def check_security_headers(self):
        """Check if security headers are properly implemented."""
        return self.run_command(
            "python -c \"import app; print('Security headers middleware:', hasattr(app, 'add_security_headers'))\"",
            "Security Headers Check",
            "security_headers_check"
        )
    
    def generate_report(self):
        """Generate a detailed security report."""
        print("\n" + "=" * 60)
        print("🔒 SECURITY MONITORING REPORT")
        print("=" * 60)
        
        # Summary
        total_checks = len(self.results["checks"])
        passed_checks = sum(1 for check in self.results["checks"].values() if check["status"] == "PASS")
        failed_checks = total_checks - passed_checks
        
        print(f"\n📊 SUMMARY:")
        print(f"   Overall Status: {self.results['overall_status']}")
        print(f"   Total Checks: {total_checks}")
        print(f"   Passed: {passed_checks}")
        print(f"   Failed: {failed_checks}")
        
        # Detailed results
        print(f"\n📋 DETAILED RESULTS:")
        for check_name, result in self.results["checks"].items():
            status_icon = "✅" if result["status"] == "PASS" else "❌"
            print(f"   {status_icon} {check_name}: {result['status']}")
        
        # Warnings
        if self.results["warnings"]:
            print(f"\n⚠️  WARNINGS:")
            for warning in self.results["warnings"]:
                print(f"   - {warning}")
        
        # Errors
        if self.results["errors"]:
            print(f"\n🚨 ERRORS:")
            for error in self.results["errors"]:
                print(f"   - {error}")
        
        # Recommendations
        if failed_checks > 0:
            self.results["recommendations"] = [
                "Review failed security tests and fix issues",
                "Update dependencies if vulnerabilities found",
                "Check security headers implementation",
                "Verify input validation and sanitization",
                "Review error handling for information disclosure"
            ]
        
        if self.results["recommendations"]:
            print(f"\n💡 RECOMMENDATIONS:")
            for rec in self.results["recommendations"]:
                print(f"   - {rec}")
        
        # Save report to file
        report_file = f"security_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        return self.results["overall_status"] == "PASS"
    
    def run_all_checks(self):
        """Run all security checks."""
        print("🔒 Workout Timer Security Monitor")
        print("=" * 60)
        print(f"Started at: {self.results['timestamp']}")
        
        # Run all checks
        checks = [
            self.run_security_audit,
            self.run_dev_security_audit,
            self.run_basic_security_tests,
            self.run_advanced_security_tests,
            self.run_app_tests,
            self.check_security_headers
        ]
        
        for check in checks:
            check()
        
        # Generate report
        success = self.generate_report()
        
        # Exit with appropriate code for CI/CD
        return 0 if success else 1

def main():
    """Main function."""
    monitor = SecurityMonitor()
    return monitor.run_all_checks()

if __name__ == "__main__":
    sys.exit(main())
