import os
import time

import redis
from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# Variables d'environnement (donnees par Docker / la CI)
VERSION = os.getenv("APP_VERSION", "dev")
GIT_SHA = os.getenv("GIT_SHA", "local")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = FastAPI()
db = redis.Redis.from_url(REDIS_URL)

# --- Metriques Prometheus ---
REQUESTS = Counter("http_requests_total", "Nombre de requetes", ["endpoint", "code"])
LATENCY = Histogram("http_request_duration_seconds", "Duree des requetes", ["endpoint"])
APP_INFO = Gauge("app_info", "Version deployee", ["version", "sha"])
APP_INFO.labels(version=VERSION, sha=GIT_SHA).set(1)


@app.middleware("http")
async def mesurer(request: Request, call_next):
    """Pour chaque requete : on compte et on chronometre."""
    debut = time.time()
    response = await call_next(request)
    duree = time.time() - debut

    endpoint = request.url.path
    REQUESTS.labels(endpoint=endpoint, code=response.status_code).inc()
    LATENCY.labels(endpoint=endpoint).observe(duree)
    return response


@app.get("/")
def accueil():
    return {"message": "Hello DevOps", "version": VERSION, "sha": GIT_SHA}


@app.get("/health")
def health():
    """L'app est en bonne sante seulement si Redis repond."""
    try:
        db.ping()
        return {"status": "ok"}
    except redis.RedisError:
        return Response(content='{"status": "ko"}', status_code=503)


@app.post("/visits")
def ajouter_visite():
    """Incremente un compteur stocke dans Redis."""
    total = db.incr("visits")
    return {"visits": total}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
