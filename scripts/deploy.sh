#!/usr/bin/env bash
# Déploie IMAGE:TAG avec docker compose, vérifie la santé et rollback sur le SHA précédent si KO.
set -euo pipefail

: "${IMAGE:?IMAGE requis (ex: ghcr.io/wacim000/devops-eval)}"
: "${TAG:?TAG requis (SHA court)}"
APP_PORT="${APP_PORT:-8000}"
HEALTH_PATH="${HEALTH_PATH:-/health}"
STATE_DIR="${DEPLOY_STATE_DIR:-$HOME/.devops-eval}"
STATE_FILE="$STATE_DIR/current_tag"

mkdir -p "$STATE_DIR"
PREVIOUS_TAG="$(cat "$STATE_FILE" 2>/dev/null || true)"
export APP_PORT

deploy() {
  local tag="$1"
  echo "==> Déploiement de ${IMAGE}:${tag}"
  APP_IMAGE="${IMAGE}:${tag}" docker compose -p devops-eval pull --quiet
  APP_IMAGE="${IMAGE}:${tag}" docker compose -p devops-eval up -d --no-build --remove-orphans
}

healthcheck() {
  local expected_sha="$1" path="$2" body
  echo "==> Healthcheck http://localhost:${APP_PORT}${path} (3 retries)"
  body="$(curl --fail --silent --show-error \
    --retry 3 --retry-delay 5 --retry-all-errors --max-time 5 \
    "http://localhost:${APP_PORT}${path}")" || return 1
  echo "$body"
  # On vérifie aussi que c'est bien la nouvelle version qui répond
  grep -q "\"sha\":\"${expected_sha}\"" <<<"$body" || {
    echo "SHA inattendu (attendu ${expected_sha})"
    return 1
  }
}

deploy "$TAG"
if healthcheck "$TAG" "$HEALTH_PATH"; then
  echo "$TAG" > "$STATE_FILE"
  echo "Déploiement OK : ${TAG} (précédent : ${PREVIOUS_TAG:-aucun})"
  exit 0
fi

echo "::error::Healthcheck KO pour ${TAG}"
if [ -n "$PREVIOUS_TAG" ] && [ "$PREVIOUS_TAG" != "$TAG" ]; then
  echo "==> Rollback vers ${PREVIOUS_TAG}"
  deploy "$PREVIOUS_TAG"
  if healthcheck "$PREVIOUS_TAG" /health; then
    echo "::warning::Rollback effectué vers ${PREVIOUS_TAG}"
  else
    echo "::error::Rollback vers ${PREVIOUS_TAG} également KO"
  fi
else
  echo "::warning::Aucune version précédente connue, rollback impossible"
fi
exit 1
