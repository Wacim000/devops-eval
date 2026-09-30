# devops-eval

Projet pour l'évaluation DevOps : une petite API (FastAPI + Redis) avec Docker, une CI, un CD avec déploiement réel et des métriques Prometheus.

## L'application

| Route | Rôle |
|-------|------|
| `GET /` | message + version |
| `GET /health` | 200 si Redis répond, 503 sinon |
| `POST /visits` | ajoute 1 à un compteur stocké dans Redis |
| `GET /metrics` | métriques Prometheus |

## Lancer en local

```bash
git clone https://github.com/Wacim000/devops-eval.git
cd devops-eval
docker compose up -d --build

curl http://localhost:8000/health
curl -X POST http://localhost:8000/visits
curl http://localhost:8000/metrics
# Prometheus : http://localhost:9090  (onglet Alerts)

docker compose down
```

Lancer les tests sans Docker (il faut un Redis sur le port 6379) :

```bash
docker run -d -p 6379:6379 redis:7.4-alpine
pip install -r requirements-dev.txt
python -m pytest
```

## Fichiers

| Fichier | Rôle |
|---------|------|
| `app/main.py` | l'API et les métriques |
| `tests/test_app.py` | 3 tests qui utilisent un vrai Redis |
| `Dockerfile` | image en 2 étapes, utilisateur non-root, HEALTHCHECK |
| `docker-compose.yml` | app + redis + prometheus |
| `monitoring/` | config Prometheus + 2 règles d'alerte |
| `.github/actions/setup-python-deps` | action locale : installe Python + cache + dépendances |
| `.github/workflows/ci.yml` | la CI |
| `.github/workflows/cd.yml` | le CD |
| `scripts/deploy.sh` | déploiement + healthcheck + rollback |

## CI

Lancée à chaque push sur `main` et à chaque pull request.

1. **lint** : `ruff` (Python) et `yamllint` (fichiers YAML)
2. **test** : tests sur Python 3.11 et 3.12 (matrix), avec un service Redis. Le rapport JUnit est envoyé avec `upload-artifact`.
3. **build** : récupère les rapports (`download-artifact`) et construit l'image Docker
4. **ci-ok** : échoue si un job a échoué. C'est ce check qui est obligatoire pour merger sur `main`.

Le cache pip est géré par `actions/setup-python` (`cache: pip`). Au 2e run, les logs affichent `Cache restored`.

## CD

Lancé à chaque push sur `main`, ou à la main (`workflow_dispatch`).

1. **ci** : relance la CI. Si elle n'est pas verte, on s'arrête.
2. **build-push** : construit l'image et la pousse sur `ghcr.io/wacim000/devops-eval` avec 3 tags : `latest`, le SHA court du commit et une version `1.0.<numéro du run>`.
3. **deploy** : sur ma machine (runner self-hosted), lance `scripts/deploy.sh` :
   - récupère la nouvelle image et relance les conteneurs,
   - teste `/health` avec `curl` (3 essais),
   - si ça échoue : redéploie l'ancienne version (rollback) et le job échoue.

Pour tester le rollback : lancer le CD à la main en cochant `simuler_panne`.

La connexion au registry se fait uniquement avec `GITHUB_TOKEN` : aucun autre secret.

## Métriques et alertes

- `http_requests_total{endpoint, code}` : nombre de requêtes
- `http_request_duration_seconds{endpoint}` : histogramme de durée, qui permet de calculer le p95
- `app_info{version, sha}` : version déployée

Alertes dans `monitoring/alerts.yml` :

| Alerte | Condition | for | Pourquoi |
|--------|-----------|-----|----------|
| TauxErreurs5xxEleve | plus de 5 % de réponses 5xx sur 5 min | 5m | 1 requête sur 20 qui plante, les utilisateurs le voient. `for: 5m` ignore les pics courts, par exemple pendant un redémarrage. |
| LatenceP95Elevee | p95 > 500 ms | 10m | Normalement moins de 50 ms, donc 10 fois plus lent. La latence varie beaucoup, on attend qu'elle reste haute longtemps. |
