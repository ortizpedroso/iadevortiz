#!/usr/bin/env bash
# Login no dashboard 9Router + cria API key + recarrega PKF.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pkf}"
cd "$APP_DIR"

if ! docker compose --profile router ps ninerouter --status running -q 2>/dev/null | grep -q .; then
  echo "==> Subindo 9Router"
  docker compose --profile router up -d ninerouter
  sleep 3
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "Erro: curl não encontrado no host. Instale: apt-get install -y curl"
  exit 1
fi

COOKIE_JAR=$(mktemp)
trap 'rm -f "$COOKIE_JAR"' EXIT

DASH_PASS="${NINEROUTER_DASHBOARD_PASSWORD:-}"
if [ -z "$DASH_PASS" ]; then
  DASH_PASS=$(docker compose exec -T ninerouter printenv INITIAL_PASSWORD 2>/dev/null | tr -d '\r' || true)
fi
DASH_PASS="${DASH_PASS:-123456}"

echo "==> Login no dashboard 9Router (http://127.0.0.1:20128)"
LOGIN=$(curl -s -c "$COOKIE_JAR" -X POST http://127.0.0.1:20128/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"password\":\"${DASH_PASS}\"}")

if ! echo "$LOGIN" | grep -q '"success":true'; then
  echo "Login falhou. Resposta:"
  echo "$LOGIN"
  echo ""
  echo "Se você trocou a senha do dashboard, rode:"
  echo "  NINEROUTER_DASHBOARD_PASSWORD='sua_senha' bash deploy/hostinger/fix-ninerouter-key.sh"
  echo ""
  echo "Ou acesse via túnel no PC:"
  echo "  ssh -L 20128:127.0.0.1:20128 root@VPS"
  echo "  http://localhost:20128/dashboard/endpoint"
  exit 1
fi

echo "==> Buscando chaves existentes"
EXISTING=$(curl -s -b "$COOKIE_JAR" http://127.0.0.1:20128/api/keys || true)
KEY=$(python3 - <<'PY' "$EXISTING"
import json, sys
raw = (sys.argv[1] or "").strip()
if not raw:
    print("")
    raise SystemExit
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print("")
    raise SystemExit
items = data if isinstance(data, list) else data.get("keys") or data.get("data") or []
for item in items:
    if not isinstance(item, dict):
        continue
    value = item.get("key") or item.get("apiKey") or item.get("api_key")
    if value:
        print(value)
        break
PY
)

if [ -z "$KEY" ]; then
  echo "==> Criando nova API key"
  RESP=$(curl -s -b "$COOKIE_JAR" -X POST http://127.0.0.1:20128/api/keys \
    -H "Content-Type: application/json" \
    -d '{"name":"pkf-vps"}')
  KEY=$(python3 - <<'PY' "$RESP"
import json, sys
raw = sys.argv[1]
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print("")
    sys.exit(0)
print(data.get("key") or data.get("apiKey") or data.get("api_key") or "")
PY
  )
fi

if [ -z "$KEY" ]; then
  echo "Falha ao obter/criar chave."
  echo "Keys GET: $EXISTING"
  echo "Keys POST: ${RESP:-}"
  exit 1
fi

echo "==> API key: ${KEY:0:15}..."

grep -q '^NINEROUTER_URL=' .env || echo 'NINEROUTER_URL=http://ninerouter:20128' >> .env
if grep -q '^NINEROUTER_KEY=' .env; then
  sed -i "s|^NINEROUTER_KEY=.*|NINEROUTER_KEY=${KEY}|" .env
else
  echo "NINEROUTER_KEY=${KEY}" >> .env
fi
sed -i '/^NINEROUTER_KEY=local$/d' .env

echo "==> Recriando PKF"
docker compose --profile router up -d pkf --force-recreate

echo "==> Aguardando health..."
for _ in $(seq 1 20); do
  if curl -sf http://127.0.0.1:8765/api/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "==> Resultado"
python3 - <<'PY'
import json, urllib.request
try:
    data = json.load(urllib.request.urlopen("http://127.0.0.1:8765/api/health", timeout=8))
    print("ninerouter_ok:", data.get("ninerouter_ok"))
    if data.get("ninerouter_error"):
        print("ninerouter_error:", data.get("ninerouter_error"))
except Exception as exc:
    print("health check falhou:", exc)
PY

echo ""
echo "Dashboard (Providers → OpenCode Free):"
echo "  ssh -L 20128:127.0.0.1:20128 root@VPS  →  http://localhost:20128/dashboard"
echo "Troque a senha padrão 123456 se ainda não trocou."
