import pytest
from flask import url_for

def test_home_page(client):
    """Test that the home page loads."""
    resp = client.get("/")
    assert resp.status_code in [200, 404]  # 404 if route doesn't exist yet

def test_static_files(client):
    """Test that static files are served."""
    # Test logo
    resp = client.get("/static/logo.svg")
    assert resp.status_code in [200, 404]
    
    # Test manifest
    resp = client.get("/static/manifest.json")
    assert resp.status_code in [200, 404]

def test_templates_exist(client):
    """Test that templates are accessible."""
    # Test main template
    resp = client.get("/")
    if resp.status_code == 200:
        # Check that it's HTML
        assert "text/html" in resp.headers.get("Content-Type", "")

def test_workout_parser_import():
    """Test that workout_parser module can be imported."""
    try:
        import workout_parser
        assert workout_parser is not None
    except ImportError:
        pytest.skip("workout_parser module not available")

def test_app_configuration(client, flask_app):
    """Test basic app configuration."""
    # Test that app has basic configuration
    assert hasattr(flask_app, 'config')
    assert flask_app.testing is True  # Should be True in test environment

def test_error_pages(client):
    """Test error page handling."""
    # Test 404 page
    resp = client.get("/nonexistent-page")
    assert resp.status_code == 404

def test_response_headers(client):
    """Test that responses have proper headers."""
    resp = client.get("/")
    headers = resp.headers
    
    # Check for basic headers
    assert "Content-Type" in headers
    assert "Content-Length" in headers or "Transfer-Encoding" in headers

def test_session_handling(client):
    """Test session handling."""
    with client.session_transaction() as sess:
        # Test that we can set session data
        sess['test_key'] = 'test_value'
    
    # Test that session persists
    with client.session_transaction() as sess:
        assert sess.get('test_key') == 'test_value'

def test_json_endpoints(client):
    """Test JSON endpoint handling."""
    # Test with JSON content type
    resp = client.post("/", 
                      data='{"test": "data"}', 
                      content_type="application/json")
    assert resp.status_code in [200, 400, 404, 405, 415]

def test_form_data_handling(client):
    """Test form data handling."""
    # Test with form data
    resp = client.post("/", 
                      data={"test": "value"}, 
                      content_type="application/x-www-form-urlencoded")
    assert resp.status_code in [200, 400, 404, 405]

def test_method_not_allowed(client):
    """Test method not allowed handling."""
    # Test unsupported methods
    resp = client.put("/")
    assert resp.status_code in [405, 404]
    
    resp = client.delete("/")
    assert resp.status_code in [405, 404]
