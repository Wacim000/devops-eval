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
"""API minimale instrumentée : santé, compteur Redis et métriques Prometheus."""

import os
import time

import redis
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

APP_VERSION = os.getenv("APP_VERSION", "0.0.0-dev")
GIT_SHA = os.getenv("GIT_SHA", "local")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

registry = CollectorRegistry()

REQUESTS = Counter(
    "http_requests_total",
    "Nombre total de requêtes HTTP reçues",
    ["method", "endpoint", "code"],
    registry=registry,
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "Durée des requêtes HTTP (secondes), par route",
    ["endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=registry,
)
BUILD_INFO = Gauge(
    "app_build_info",
    "Version et SHA du commit actuellement déployé (valeur toujours 1)",
    ["version", "sha"],
    registry=registry,
)
BUILD_INFO.labels(version=APP_VERSION, sha=GIT_SHA).set(1)

app = FastAPI(title="devops-eval", version=APP_VERSION)
store = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=2, socket_timeout=2)


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        # On utilise le template de route (/items/{id}) pour éviter l'explosion de cardinalité
        route = request.scope.get("route")
        endpoint = getattr(route, "path", "unmatched")
        if endpoint != "/metrics":
            LATENCY.labels(endpoint=endpoint).observe(time.perf_counter() - start)
        REQUESTS.labels(method=request.method, endpoint=endpoint, code=str(status)).inc()


@app.get("/")
def root():
    return {"app": "devops-eval", "version": APP_VERSION, "sha": GIT_SHA}


@app.get("/health")
def health():
    """Santé réelle : l'app répond ET sa dépendance Redis est joignable."""
    try:
        store.ping()
    except redis.RedisError as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "redis": "down", "error": type(exc).__name__},
        )
    return {"status": "ok", "redis": "up", "version": APP_VERSION, "sha": GIT_SHA}


@app.post("/hits")
def add_hit():
    """Incrémente un compteur persistant dans Redis."""
    return {"hits": int(store.incr("hits"))}


@app.get("/hits")
def get_hits():
    value = store.get("hits")
    return {"hits": int(value) if value else 0}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
