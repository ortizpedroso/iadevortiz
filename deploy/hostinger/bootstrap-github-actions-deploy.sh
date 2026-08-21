#!/usr/bin/env bash
# Gera chave SSH dedicada ao GitHub Actions e imprime o que cadastrar nos Secrets.
set -euo pipefail

KEY_DIR="${KEY_DIR:-$HOME/.ssh}"
KEY_PATH="$KEY_DIR/github_actions_pkf_deploy"
PUB_PATH="${KEY_PATH}.pub"

mkdir -p "$KEY_DIR"
chmod 700 "$KEY_DIR"

if [[ ! -f "$KEY_PATH" ]]; then
  ssh-keygen -t ed25519 -f "$KEY_PATH" -N "" -C "github-actions-pkf-deploy"
  echo "Chave criada: $KEY_PATH"
else
  echo "Chave já existe: $KEY_PATH"
fi

chmod 600 "$KEY_PATH"
chmod 644 "$PUB_PATH"

# Garante que deploy via Actions consegue entrar (mesma chave no authorized_keys).
AUTH_KEYS="$HOME/.ssh/authorized_keys"
PUB_LINE="$(cat "$PUB_PATH")"
if [[ -f "$AUTH_KEYS" ]] && grep -Fq "$PUB_LINE" "$AUTH_KEYS"; then
  echo "authorized_keys: chave já presente."
else
  echo "$PUB_LINE" >> "$AUTH_KEYS"
  chmod 600 "$AUTH_KEYS"
  echo "authorized_keys: chave adicionada."
fi

HOST="$(curl -4 -fsS --max-time 5 ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"

cat <<EOF

=== GitHub → Settings → Secrets and variables → Actions → New repository secret ===

VPS_HOST        = ${VPS_HOST:-$HOST}
VPS_USER        = ${VPS_USER:-$(whoami)}
VPS_SSH_KEY     = (cole o conteúdo COMPLETO de $KEY_PATH abaixo)
VPS_PORT        = 22                    (opcional)
VPS_HEALTHCHECK_URL = http://${VPS_HOST:-$HOST}:8765/api/health   (opcional; ou URL HTTPS do Caddy)

--- INÍCIO VPS_SSH_KEY (copie tudo, incluindo BEGIN/END) ---
$(cat "$KEY_PATH")
--- FIM VPS_SSH_KEY ---

Depois de salvar os secrets, em Actions → Deploy to VPS → Run workflow (ou push na main).

Alternativa sem Actions: bash deploy/hostinger/install-cron-deploy.sh
EOF
