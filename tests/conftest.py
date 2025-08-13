import os
import pytest
import importlib
from types import ModuleType

def _import_app_module():
    # Try common entry points in order
    candidates = ["app", "wsgi", "main"]
    last_err = None
    for name in candidates:
        try:
            return importlib.import_module(name)
        except Exception as e:
            last_err = e
    raise last_err or ImportError("Could not import app module (tried app.py, wsgi.py, main.py)")

@pytest.fixture(scope="session")
def flask_app():
    """
    Resolve a Flask app instance. Supports:
      - module-level `app = Flask(__name__)`
      - factory `create_app()`
    """
    mod: ModuleType = _import_app_module()
    # App instance at module level
    app = getattr(mod, "app", None)
    if app is not None:
        return app
    # Factory
    factory = getattr(mod, "create_app", None)
    if callable(factory):
        return factory()
    raise RuntimeError("Neither `app` nor `create_app()` found in your entry module.")

@pytest.fixture(autouse=True)
def test_env(tmp_path, monkeypatch):
    """Set safe defaults for tests (no real secrets)."""
    monkeypatch.setenv("FLASK_SECRET_KEY", "test_" + "a"*64)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("WHOOP_CLIENT_ID", "whoop-test-id")
    monkeypatch.setenv("WHOOP_CLIENT_SECRET", "whoop-test-secret")
    monkeypatch.setenv("ENCRYPTION_KEY", "mzU2Y2x3eGt5enFCR1ZKU2RsRkRkM2hVeHNWQ0RvR0g=")  # dummy Fernet key (base64)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    # Avoid HTTPS redirect during tests unless explicitly enabled
    monkeypatch.setenv("FLASK_ENV", "development")

@pytest.fixture
def client(flask_app):
    flask_app.testing = True
    return flask_app.test_client()
