# ---------- Étape 1 : build des dépendances dans un venv ----------
FROM python:3.12.7-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------- Étape 2 : image finale minimale, non-root ----------
FROM python:3.12.7-slim-bookworm AS runtime

ARG APP_VERSION=0.0.0-dev
ARG GIT_SHA=local

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION} \
    GIT_SHA=${GIT_SHA} \
    PORT=8000

LABEL org.opencontainers.image.source="https://github.com/Wacim000/devops-eval" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}"

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /srv
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app app/ ./app/

USER app

EXPOSE 8000

# /health renvoie 503 si Redis est injoignable -> le conteneur passe "unhealthy"
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
