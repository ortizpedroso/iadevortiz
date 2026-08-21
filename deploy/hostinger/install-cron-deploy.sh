#!/usr/bin/env bash
# Instala cron na VPS: verifica origin/main a cada 5 min e roda update.sh se mudou.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pkf}"
SCRIPT="$APP_DIR/deploy/hostinger/watch-and-deploy.sh"
CRON_LINE="*/5 * * * * APP_DIR=$APP_DIR $SCRIPT >> /var/log/pkf-deploy.log 2>&1"

if [[ ! -x "$SCRIPT" ]]; then
  echo "Erro: $SCRIPT não encontrado ou não executável. Rode git pull em $APP_DIR primeiro."
  exit 1
fi

touch /var/log/pkf-deploy.log
chmod 644 /var/log/pkf-deploy.log 2>/dev/null || true

if crontab -l 2>/dev/null | grep -Fq "watch-and-deploy.sh"; then
  echo "Cron de deploy PKF já instalado."
else
  (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
  echo "Cron instalado (a cada 5 min):"
  echo "  $CRON_LINE"
fi

echo "Log: /var/log/pkf-deploy.log"
echo "Teste manual: APP_DIR=$APP_DIR bash $SCRIPT"
