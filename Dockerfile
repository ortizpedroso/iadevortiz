# syntax=docker/dockerfile:1

FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PKF_ENV=production \
    PKF_HOST=0.0.0.0 \
    PKF_PORT=8765 \
    PKF_NO_BROWSER=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-prod.txt pyproject.toml ./
COPY pkf ./pkf
COPY --from=frontend /frontend/dist ./frontend/dist

RUN pip install --no-cache-dir -r requirements-prod.txt \
    && pip install --no-cache-dir .

RUN useradd --create-home --shell /bin/bash pkf \
    && mkdir -p /data/workspace \
    && chown -R pkf:pkf /data /app

USER pkf
WORKDIR /data/workspace

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health')" || exit 1

CMD ["python", "-m", "pkf", "--ui", "--host", "0.0.0.0", "--workspace", "/data/workspace"]
