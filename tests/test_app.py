"""Tests d'intégration : ils utilisent un vrai Redis (service CI ou docker compose)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app, store


@pytest.fixture(autouse=True)
def clean_redis():
    store.delete("hits")
    yield
    store.delete("hits")


@pytest.fixture
def client():
    return TestClient(app)


def test_health_reports_redis_up(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["redis"] == "up"


def test_hits_are_persisted_in_redis(client):
    assert client.get("/hits").json() == {"hits": 0}
    assert client.post("/hits").json() == {"hits": 1}
    assert client.post("/hits").json() == {"hits": 2}
    # la valeur est bien stockée dans Redis, pas en mémoire
    assert int(store.get("hits")) == 2
    assert client.get("/hits").json() == {"hits": 2}


def test_health_returns_503_when_redis_is_down(client, monkeypatch):
    import redis

    def boom():
        raise redis.ConnectionError("down")

    monkeypatch.setattr(store, "ping", boom)
    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["redis"] == "down"


def test_metrics_expose_counter_histogram_and_build_info(client):
    client.get("/health")
    client.get("/does-not-exist")
    text = client.get("/metrics").text
    assert 'http_requests_total{code="200",endpoint="/health",method="GET"}' in text
    assert 'code="404",endpoint="unmatched"' in text
    assert 'http_request_duration_seconds_bucket{endpoint="/health"' in text
    assert "app_build_info{" in text
