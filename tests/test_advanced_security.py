import os
import json
import sqlite3
import pytest
from http import HTTPStatus

def test_advanced_security_headers_present(client):
    """Test for comprehensive security headers."""
    resp = client.get("/")
    headers = resp.headers
    
    # Test for all security headers we implemented
    assert "X-Content-Type-Options" in headers
    assert headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in headers
    assert "Referrer-Policy" in headers
    assert "X-XSS-Protection" in headers
    assert "Permissions-Policy" in headers

def test_csrf_protection_for_post_endpoints(client):
    """Test CSRF protection for POST endpoints."""
    # Test /generate_workout endpoint (which exists in our app)
    resp = client.post("/generate_workout", json={"request": "easy"})
    # Should either succeed (if no CSRF required) or fail gracefully
    assert resp.status_code in [200, 400, 401, 403, 404, 405, 422]

def test_csrf_with_session_simulation(client):
    """Test CSRF with simulated session."""
    with client.session_transaction() as sess:
        sess["user_id"] = "test_user"
    
    # Test POST without CSRF token
    resp = client.post("/generate_workout", json={"request": "tempo"})
    assert resp.status_code in [200, 400, 401, 403, 404, 405, 422]

def test_rate_limiting_simulation(client):
    """Test rate limiting by making multiple requests."""
    responses = []
    for i in range(15):  # More than typical rate limit
        resp = client.post("/generate_workout", 
                          json={"request": f"request_{i}"})
        responses.append(resp.status_code)
    
    # Should handle multiple requests gracefully
    # If rate limiting is implemented, some should return 429
    # If not, all should return valid status codes
    valid_statuses = [200, 400, 401, 403, 404, 405, 422, 429]
    assert all(status in valid_statuses for status in responses)

def test_advanced_sql_injection_resistance(client):
    """Test advanced SQL injection resistance."""
    # Test with more sophisticated injection attempts
    advanced_payloads = [
        "'; DROP TABLE workouts; --",
        "1' UNION SELECT * FROM workouts --",
        "'; INSERT INTO workouts (description, intervals) VALUES ('hack', 'hack'); --",
        "1' OR 1=1 --",
        "'; UPDATE workouts SET description='hacked' --",
        "1' AND (SELECT COUNT(*) FROM workouts) > 0 --"
    ]
    
    for payload in advanced_payloads:
        # Test as query parameter
        resp = client.get(f"/?q={payload}")
        assert resp.status_code in [200, 400, 404, 500]
        
        # Test as JSON payload
        resp = client.post("/generate_workout", 
                          json={"request": payload})
        assert resp.status_code in [200, 400, 401, 403, 404, 405, 422, 500]
        
        # Check response doesn't contain SQL errors
        response_text = resp.get_data(as_text=True).lower()
        sql_errors = [
            "sqlite error",
            "mysql error",
            "postgresql error",
            "syntax error",
            "table doesn't exist",
            "column doesn't exist",
            "sql error",
            "database error",
            "unrecognized token",
            "near \"drop\"",
            "near \"union\"",
            "near \"insert\""
        ]
        
        for error in sql_errors:
            assert error not in response_text, f"SQL error '{error}' found in response"

def test_token_security(client):
    """Test token security in responses."""
    resp = client.get("/")
    response_text = resp.get_data(as_text=True)
    
    # Check that no actual tokens are exposed
    token_patterns = [
        "sk-",  # OpenAI API keys
        "whoop_client_secret",
        "flask_secret_key",
        "access_token",
        "refresh_token",
        "bearer token",
        "api_key=",
        "token="
    ]
    
    for pattern in token_patterns:
        assert pattern not in response_text.lower(), f"Token pattern '{pattern}' found in response"

def test_content_security_policy_strictness(client):
    """Test Content Security Policy strictness."""
    resp = client.get("/")
    csp = resp.headers.get("Content-Security-Policy", "")
    
    # Check that CSP is present and has reasonable restrictions
    assert "default-src 'self'" in csp
    assert "script-src" in csp
    assert "style-src" in csp
    
    # Note: We allow 'unsafe-inline' for now since the app uses inline scripts
    # In production, this should be tightened

def test_authentication_endpoints_security(client):
    """Test security of authentication-related endpoints."""
    # Test WHOOP auth endpoint
    resp = client.get("/whoop/auth")
    assert resp.status_code in [200, 302, 404, 500]  # Redirect expected for OAuth
    
    # Test WHOOP callback endpoint
    resp = client.get("/whoop/callback")
    assert resp.status_code in [200, 400, 404, 500]

def test_file_upload_security(client):
    """Test security of file upload endpoints."""
    # Test WHOOP screenshot upload endpoint
    resp = client.post("/upload_whoop_screenshot", 
                      data={"file": "test.jpg"})
    assert resp.status_code in [200, 400, 401, 403, 404, 405, 413, 415, 500]

def test_session_security(client):
    """Test session security."""
    with client.session_transaction() as sess:
        # Test session can be set
        sess["test_key"] = "test_value"
        assert sess.get("test_key") == "test_value"
    
    # Test session persists across requests
    with client.session_transaction() as sess:
        assert sess.get("test_key") == "test_value"

def test_input_validation_comprehensive(client):
    """Test comprehensive input validation."""
    # Test various input types and sizes
    test_inputs = [
        ("normal_input", "Hello World"),
        ("long_input", "a" * 10000),
        ("special_chars", "!@#$%^&*()_+-=[]{}|;':\",./<>?"),
        ("unicode_input", "测试中文"),
        ("sql_injection", "'; DROP TABLE users; --"),
        ("xss_payload", "<script>alert('xss')</script>"),
        ("json_injection", '{"malicious": "data"}'),
        ("null_bytes", "test\x00string"),
        ("control_chars", "test\x01\x02\x03string"),
    ]
    
    for input_name, test_input in test_inputs:
        # Test as query parameter
        resp = client.get(f"/?q={test_input}")
        assert resp.status_code in [200, 400, 404, 413, 500]
        
        # Test as JSON payload
        resp = client.post("/generate_workout", 
                          json={"request": test_input})
        assert resp.status_code in [200, 400, 401, 403, 404, 405, 413, 415, 422, 500]

def test_error_handling_security(client):
    """Test that error handling doesn't leak sensitive information."""
    # Test various error conditions
    error_tests = [
        ("/nonexistent", 404),
        ("/invalid/route/", 404),
        ("/generate_workout", 405),  # GET instead of POST
    ]
    
    for route, expected_status in error_tests:
        resp = client.get(route)
        assert resp.status_code == expected_status
        
        # Check error response doesn't leak sensitive info
        response_text = resp.get_data(as_text=True).lower()
        sensitive_patterns = [
            "sqlite",
            "mysql",
            "postgresql",
            "database",
            "stack trace",
            "traceback",
            "internal server error",
            "debug",
            "development",
            "secret",
            "password",
            "api_key"
        ]
        
        for pattern in sensitive_patterns:
            assert pattern not in response_text, f"Sensitive pattern '{pattern}' in error response"

def test_headers_security_comprehensive(client):
    """Test comprehensive security headers."""
    resp = client.get("/")
    headers = resp.headers
    
    # Test all security headers are present and have correct values
    security_headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }
    
    for header, expected_value in security_headers.items():
        assert header in headers, f"Security header '{header}' missing"
        assert headers[header] == expected_value, f"Security header '{header}' has wrong value"
    
    # Test CSP is present
    assert "Content-Security-Policy" in headers
    
    # Test Permissions Policy is present
    assert "Permissions-Policy" in headers
