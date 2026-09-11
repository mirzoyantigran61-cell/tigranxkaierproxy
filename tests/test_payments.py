def test_products_public(app_client):
    r = app_client.get("/api/payments/products")
    assert r.status_code == 200


def test_payment_create_requires_session(app_client):
    r = app_client.post("/api/payments/create", json={})
    assert r.status_code == 401


def test_payment_get_requires_session(app_client):
    r = app_client.get("/api/payments/order_x")
    assert r.status_code == 401
