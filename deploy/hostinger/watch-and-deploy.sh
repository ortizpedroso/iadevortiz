#!/usr/bin/env bash
# Pull + update quando origin/main avançar (cron/systemd na VPS).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pkf}"
LOG="${PKF_DEPLOY_LOG:-/var/log/pkf-deploy.log}"

cd "$APP_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "$(date -Is) ERRO: $APP_DIR não é repositório git" | tee -a "$LOG"
  exit 1
fi

git fetch origin main --quiet
LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse origin/main)"

if [[ "$LOCAL" == "$REMOTE" ]]; then
  exit 0
fi

{
  echo "$(date -Is) Deploy: $LOCAL -> $REMOTE"
  git pull origin main
  bash deploy/hostinger/update.sh
  echo "$(date -Is) OK"
} 2>&1 | tee -a "$LOG"
