import os
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("FIREBASE_SERVICE_ACCOUNT_JSON", "")


@pytest.fixture
def app_client():
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
