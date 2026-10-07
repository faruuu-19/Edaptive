def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_openapi_builds(client):
    assert "/api/events" in client.get("/openapi.json").json()["paths"]
