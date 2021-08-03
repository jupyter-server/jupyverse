import pytest
from fastapi.testclient import TestClient
from fps.main import app


@pytest.fixture()
def client():
    return TestClient(app)
