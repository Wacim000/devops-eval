from fastapi.testclient import TestClient

from app.main import app, db

client = TestClient(app)


def test_health_ok_quand_redis_repond():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_visits_incremente_le_compteur_dans_redis():
    db.delete("visits")

    assert client.post("/visits").json() == {"visits": 1}
    assert client.post("/visits").json() == {"visits": 2}

    # On verifie directement dans Redis que la valeur est bien stockee
    assert int(db.get("visits")) == 2


def test_metrics_contient_le_compteur_de_requetes():
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
