def test_ai_requires_session(app_client):
    r = app_client.post("/api/ai/chat", json={"message": "hi"})
    assert r.status_code == 401


def test_chats_requires_session(app_client):
    r = app_client.get("/api/ai/chats")
    assert r.status_code == 401


def test_ai_status_public(app_client):
    r = app_client.get("/api/ai/status")
    assert r.status_code == 200
    data = r.get_json()
    assert "configured" in data
