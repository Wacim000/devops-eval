# Etape 1 : on installe les dependances
FROM python:3.12.7-slim AS build
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Etape 2 : image finale, on recupere seulement ce qui a ete installe
FROM python:3.12.7-slim
WORKDIR /app
COPY --from=build /install /usr/local
COPY app/ ./app/

# Version et SHA passes au moment du build (utilises par /metrics)
ARG APP_VERSION=dev
ARG GIT_SHA=local
ENV APP_VERSION=$APP_VERSION GIT_SHA=$GIT_SHA

# On ne tourne pas en root
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# Docker appelle /health toutes les 30s (pas de curl dans l'image slim, donc python)
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
