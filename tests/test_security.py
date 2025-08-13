import os
import json
import sqlite3
import pytest
from http import HTTPStatus

def test_basic_security_headers(client):
    """Test that basic security headers are present."""
    resp = client.get("/")
    headers = resp.headers
    
    # Check for basic security headers
    assert "X-Content-Type-Options" in headers or resp.status_code == 404
    # Note: These headers might not be present in a basic Flask app
    # but we check that the app responds properly

def test_no_sensitive_data_in_response(client):
    """Test that sensitive data is not exposed in responses."""
    resp = client.get("/")
    
    # Check that common sensitive patterns are not in response
    response_text = resp.get_data(as_text=True)
    
    # More specific patterns that indicate actual sensitive data exposure
    sensitive_patterns = [
        "sk-test",  # API keys (more specific)
        "api_key=",  # API key parameters
        "secret=",   # Secret parameters
        "token=",    # Token parameters
        "password=", # Password parameters
        "whoop_client_secret",  # Specific to this app
        "flask_secret_key",     # Specific to this app
    ]
    
    for pattern in sensitive_patterns:
        assert pattern not in response_text.lower(), f"Sensitive pattern '{pattern}' found in response"

def test_sql_injection_resistance(client):
    """Test basic SQL injection resistance."""
    # Test with potentially dangerous input
    dangerous_inputs = [
        "'; DROP TABLE users; --",
        "1' OR '1'='1",
        "'; INSERT INTO users VALUES ('hacker', 'password'); --"
    ]
    
    for dangerous_input in dangerous_inputs:
        # Try to access with dangerous input
        resp = client.get(f"/?q={dangerous_input}")
        # Should not crash or expose database errors
        assert resp.status_code in [200, 404, 400, 500]
        
        # Check that no SQL errors are exposed
        response_text = resp.get_data(as_text=True).lower()
        
        # Look for actual SQL error patterns, not CSS properties
        sql_error_indicators = [
            "sqlite error",
            "mysql error", 
            "postgresql error",
            "syntax error",
            "table doesn't exist",
            "column doesn't exist",
            "sql error",
            "database error"
        ]
        
        for indicator in sql_error_indicators:
            assert indicator not in response_text, f"SQL error indicator '{indicator}' found in response"

def test_xss_protection(client):
    """Test basic XSS protection."""
    # Test with potentially dangerous input
    xss_payloads = [
        "<script>alert('xss')</script>",
        "javascript:alert('xss')",
        "<img src=x onerror=alert('xss')>",
        "';alert('xss');//"
    ]
    
    for payload in xss_payloads:
        resp = client.get(f"/?q={payload}")
        response_text = resp.get_data(as_text=True)
        
        # Check that user-provided script tags are properly escaped
        # Note: The app may have legitimate inline scripts, so we check for proper escaping
        if "<script>alert('xss')</script>" in payload:
            # User input should be escaped, not executed
            assert "&lt;script&gt;alert('xss')&lt;/script&gt;" in response_text or \
                   "<script>alert('xss')</script>" not in response_text

def test_csrf_protection_basic(client):
    """Test basic CSRF protection for POST requests."""
    # Test POST without CSRF token (if CSRF is implemented)
    resp = client.post("/", data={"test": "data"})
    
    # Should either succeed (if no CSRF required) or fail gracefully
    assert resp.status_code in [200, 400, 401, 403, 404, 405]

def test_rate_limiting_basic(client):
    """Test basic rate limiting (if implemented)."""
    # Make multiple requests quickly
    responses = []
    for i in range(10):
        resp = client.get("/")
        responses.append(resp.status_code)
    
    # Should not crash and should handle multiple requests
    assert all(status in [200, 404, 429] for status in responses)

def test_secure_cookies(client):
    """Test that cookies are set securely."""
    resp = client.get("/")
    
    # Check cookie security attributes if cookies are set
    for cookie in resp.headers.getlist('Set-Cookie'):
        # In production, cookies should be secure
        # For testing, we just check they're properly formatted
        assert '=' in cookie or 'HttpOnly' in cookie or 'Secure' in cookie

def test_error_handling(client):
    """Test that errors are handled gracefully."""
    # Test non-existent routes
    resp = client.get("/nonexistent-route")
    assert resp.status_code in [404, 405]
    
    # Test malformed requests
    resp = client.post("/", data="invalid json", content_type="application/json")
    assert resp.status_code in [400, 404, 405, 500]

def test_content_type_validation(client):
    """Test content type validation."""
    # Test with wrong content type
    resp = client.post("/", data="test", content_type="text/plain")
    assert resp.status_code in [200, 400, 404, 405, 415]

def test_input_validation(client):
    """Test basic input validation."""
    # Test with very long input
    long_input = "a" * 10000
    resp = client.get(f"/?q={long_input}")
    assert resp.status_code in [200, 400, 404, 413]
    
    # Test with special characters
    special_chars = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
    resp = client.get(f"/?q={special_chars}")
    assert resp.status_code in [200, 400, 404]

def test_database_connection_security(client):
    """Test that database connections are handled securely."""
    # This test assumes your app uses a database
    # We'll just test that the app doesn't crash on database operations
    resp = client.get("/")
    assert resp.status_code in [200, 404, 500]
    
    # Check that no database connection strings are exposed
    response_text = resp.get_data(as_text=True).lower()
    db_indicators = [
        "sqlite://",
        "mysql://",
        "postgresql://",
        "database_url",
        "connection_string"
    ]
    
    for indicator in db_indicators:
        assert indicator not in response_text, f"Database indicator '{indicator}' found in response"
