from fastapi.testclient import TestClient
from payguard.api import app

c = TestClient(app)


def test_health_ask_metrics():
    assert c.get("/health").json()["status"] == "ok"
    r = c.post("/ask", json={"question": "How long do international refunds take?"}).json()
    assert "10 to 14" in r["answer"]
    assert "payguard_requests_total" in c.get("/metrics").text


def test_validation():
    assert c.post("/ask", json={"question": "hi", "customer_id": "bad"}).status_code == 422
