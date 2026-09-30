#!/usr/bin/env bash
# Deploie la nouvelle image, verifie /health, et revient a l'ancienne si ca echoue.
set -e

NOUVEAU=${TAG::7}                                   # SHA court du commit a deployer
ANCIEN=$(cat ~/.devops-eval-version 2>/dev/null || echo "")   # SHA deploye avant

URL=http://localhost:8000/health
if [ "$SIMULER_PANNE" = "true" ]; then
  URL=http://localhost:8000/route-qui-n-existe-pas
fi

deployer() {
  echo "Deploiement de $IMAGE:$1"
  export APP_IMAGE=$IMAGE:$1
  docker compose pull app
  docker compose up -d --no-build
}

deployer "$NOUVEAU"

echo "Healthcheck sur $URL (3 essais)"
if curl --fail --retry 3 --retry-delay 5 --retry-all-errors "$URL"; then
  echo "$NOUVEAU" > ~/.devops-eval-version
  echo "Deploiement OK"
  exit 0
fi

echo "Healthcheck KO -> rollback vers $ANCIEN"
if [ -n "$ANCIEN" ]; then
  deployer "$ANCIEN"
fi
exit 1
