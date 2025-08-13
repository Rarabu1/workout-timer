# Security Monitoring Guide

This guide explains how to detect and respond to security issues in your workout timer application.

## 🚨 How You'll Know About Security Issues

### 1. **Automated Detection (Recommended)**

#### GitHub Actions Workflow
- **Location**: `.github/workflows/security-check.yml`
- **Triggers**: 
  - Every push to main/develop branches
  - Every pull request
  - Daily at 6 AM UTC (scheduled)
  - Manual trigger (workflow_dispatch)

**What happens when security issues are found:**
- ❌ **Pull Requests**: Automatic comment on PR with security alert
- ❌ **Main Branch**: Automatic GitHub issue created with high-priority label
- 📄 **Reports**: Security report saved as workflow artifact
- 🔔 **Notifications**: Email notifications (if configured in GitHub)

#### Local Development
```bash
# Quick security check
python security_alert.py

# Comprehensive security monitoring
python security_monitor.py

# Basic security check
python security_check.py
```

### 2. **Manual Detection**

#### Running Tests Manually
```bash
# Run all security tests
python -m pytest tests/test_security.py -v
python -m pytest tests/test_advanced_security.py -v

# Run specific failing test
python -m pytest tests/test_security.py::test_basic_security_headers -v

# Run with detailed output
python -m pytest tests/ -v --tb=long
```

#### Dependency Security Audit
```bash
# Check production dependencies
python -m pip_audit --requirement requirements.txt

# Check development dependencies
python -m pip_audit --requirement requirements-dev.txt

# Check all dependencies
python -m pip_audit --requirement requirements.txt --requirement requirements-dev.txt
```

## 🔍 Types of Security Issues You'll Detect

### 1. **Failed Security Tests**
- **Missing Security Headers**: X-Content-Type-Options, CSP, etc.
- **SQL Injection Vulnerabilities**: Database error exposure
- **XSS Vulnerabilities**: Script injection possibilities
- **CSRF Vulnerabilities**: Missing token validation
- **Input Validation Issues**: Malicious input handling
- **Error Information Disclosure**: Sensitive data in error messages

### 2. **Dependency Vulnerabilities**
- **Known CVEs**: Security vulnerabilities in dependencies
- **Outdated Packages**: Packages with security fixes available
- **Malicious Packages**: Packages flagged as malicious

### 3. **Configuration Issues**
- **Missing Security Headers**: Security headers not implemented
- **Weak CSP Policies**: Content Security Policy too permissive
- **Insecure Settings**: Development settings in production

## 🚨 Security Alert Examples

### Failed Security Test Alert
```
🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨
🚨 SECURITY ALERT 🚨
🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨
🚨 SECURITY TESTS FAILED!
test_basic_security_headers FAILED
test_sql_injection_resistance FAILED
🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨

🔧 IMMEDIATE ACTION REQUIRED:
   1. Review the security issue
   2. Fix the problem
   3. Re-run security checks
   4. Commit and push fixes
```

### Dependency Vulnerability Alert
```
🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨
🚨 SECURITY ALERT 🚨
🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨
🚨 DEPENDENCY VULNERABILITIES DETECTED!
Found 2 known vulnerabilities in 1 package
Name     Version ID                  Fix Versions
-------- ------- ------------------- ------------
requests 2.31.0  GHSA-9wx4-h78v-vm56 2.32.0
requests 2.31.0  GHSA-9hjg-9r4m-mvj7 2.32.4
🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨

🔧 IMMEDIATE ACTION REQUIRED:
   1. Review the security issue
   2. Fix the problem
   3. Re-run security checks
   4. Commit and push fixes
```

## 🔧 How to Respond to Security Issues

### 1. **Immediate Actions**

#### For Failed Tests
1. **Identify the Issue**: Read the test output to understand what failed
2. **Check the Test**: Look at the specific test file to understand the requirement
3. **Fix the Code**: Implement the missing security feature
4. **Test Locally**: Run the tests to ensure they pass
5. **Commit and Push**: Push the fix to trigger automated checks

#### For Dependency Vulnerabilities
1. **Update Dependencies**: Update to the recommended version
2. **Test the Update**: Ensure the app still works
3. **Check for Breaking Changes**: Review changelog if major version update
4. **Commit and Push**: Push the updated requirements

### 2. **Investigation Steps**

#### Check Security Report
```bash
# View the latest security report
ls -la security_report_*.json
cat security_report_20250113_123456.json
```

#### Run Detailed Tests
```bash
# Run specific failing test with verbose output
python -m pytest tests/test_security.py::test_basic_security_headers -vv

# Run all tests with maximum verbosity
python -m pytest tests/ -vv --tb=long
```

#### Check GitHub Actions
1. Go to your repository on GitHub
2. Click on "Actions" tab
3. Find the failed workflow run
4. Review the logs and artifacts

### 3. **Common Fixes**

#### Missing Security Headers
```python
# Add to app.py
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    # ... more headers
    return response
```

#### Dependency Updates
```bash
# Update specific package
pip install --upgrade requests

# Update requirements.txt
pip freeze > requirements.txt
```

#### Input Validation
```python
# Add proper input validation
from flask import abort
import re

def validate_input(user_input):
    if not re.match(r'^[a-zA-Z0-9\s\-_]+$', user_input):
        abort(400, "Invalid input")
```

## 📊 Monitoring Dashboard

### Security Status Indicators

#### ✅ All Good
```
✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅
✅ SECURITY STATUS: OK ✅
✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅
✅ All security checks passed!
```

#### ⚠️ Warnings
```
⚠️  WARNINGS:
   - dependency_audit: SSL warning detected
   - basic_security_tests: Some tests have warnings
```

#### 🚨 Critical Issues
```
🚨 ERRORS:
   - basic_security_tests: Security headers missing
   - dependency_audit: Critical vulnerabilities found
```

## 🔄 Continuous Monitoring

### Daily Checks
- GitHub Actions runs automatically at 6 AM UTC
- Security reports are generated and stored
- Issues are created for any failures

### Before Deployment
```bash
# Always run before deploying
python security_check.py

# For critical deployments
python security_monitor.py
```

### After Code Changes
```bash
# Quick check after any changes
python security_alert.py

# Full check before committing
python security_check.py
```

## 📞 Emergency Contacts

### For Critical Security Issues
1. **Immediate**: Stop deployment if security issues are found
2. **Investigation**: Use the monitoring tools to identify the issue
3. **Fix**: Implement the security fix
4. **Test**: Verify the fix resolves the issue
5. **Deploy**: Only deploy after all security checks pass

### Escalation
- If you can't fix the issue immediately, create a high-priority GitHub issue
- Tag the issue with `security` and `high-priority` labels
- Include the security report in the issue description

## 📚 Additional Resources

- [SECURITY_TESTING.md](./SECURITY_TESTING.md) - Detailed security testing documentation
- [GitHub Security Advisories](https://github.com/advisories) - Database of security vulnerabilities
- [OWASP Top 10](https://owasp.org/www-project-top-ten/) - Common web application security risks
- [Flask Security Documentation](https://flask-security.readthedocs.io/) - Flask security best practices
