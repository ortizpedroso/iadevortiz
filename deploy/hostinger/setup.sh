#!/usr/bin/env bash
# Instala Docker e sobe a PKF em VPS Ubuntu (Hostinger)
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pkf}"

echo "==> Atualizando pacotes"
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl git ufw

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Instalando Docker"
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose plugin necessário (incluso no Docker moderno)."
  exit 1
fi

echo "==> Preparando diretório $APP_DIR"
sudo mkdir -p "$APP_DIR"
sudo chown "$USER":"$USER" "$APP_DIR"

if [ ! -f "$APP_DIR/.env" ]; then
  echo "Copie .env.production.example para $APP_DIR/.env e preencha as chaves."
  if [ -f ".env.production.example" ]; then
    cp .env.production.example "$APP_DIR/.env.example"
  fi
fi

echo "==> Firewall (SSH + HTTP)"
sudo ufw allow OpenSSH || true
sudo ufw allow 80/tcp || true
sudo ufw --force enable || true

echo "==> Build e start"
cd "$APP_DIR"
docker compose pull nginx || true
docker compose build --no-cache
docker compose up -d

echo ""
echo "PKF no ar. Acesse: http://SEU_IP/"
echo "Com token: http://SEU_IP/?token=SEU_PKF_AUTH_TOKEN"
echo "Logs: docker compose logs -f pkf"
