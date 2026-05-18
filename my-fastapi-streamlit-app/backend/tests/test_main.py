import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_ask_endpoint():
    response = client.post("/ask", json={"question": "What is the capital of France?"})
    assert response.status_code == 200
    assert "response" in response.json()

def test_ask_endpoint_invalid_data():
    response = client.post("/ask", json={"invalid_key": "What is the capital of France?"})
    assert response.status_code == 422  # Unprocessable Entity for invalid data