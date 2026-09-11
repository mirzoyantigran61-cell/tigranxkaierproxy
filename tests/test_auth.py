def test_login_missing_creds(app_client):
    r = app_client.post("/api/login", json={})
    assert r.status_code == 400


def test_login_wrong_creds(app_client):
    r = app_client.post("/api/login", json={"username": "x", "password": "y"})
    assert r.status_code in (401, 500)


def test_me_requires_session(app_client):
    r = app_client.get("/api/me")
    assert r.status_code == 401


def test_health(app_client):
    r = app_client.get("/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
