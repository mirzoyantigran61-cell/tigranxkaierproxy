def test_admin_payments_requires_admin(app_client):
    r = app_client.get("/api/admin/payments")
    assert r.status_code == 401


def test_admin_system_requires_admin(app_client):
    r = app_client.get("/api/admin/system")
    assert r.status_code == 401
