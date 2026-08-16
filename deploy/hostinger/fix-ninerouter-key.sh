#!/usr/bin/env bash
# Cria API key no 9Router e recarrega PKF (sem túnel SSH / dashboard).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pkf}"
cd "$APP_DIR"

if ! docker compose --profile router ps ninerouter --status running -q 2>/dev/null | grep -q .; then
  echo "==> Subindo 9Router"
  docker compose --profile router up -d ninerouter
  sleep 3
fi

echo "==> Criando API key (loopback dentro do container ninerouter)"
RESP=$(docker compose exec -T ninerouter curl -s -X POST http://127.0.0.1:20128/api/keys \
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

if [ -z "$KEY" ]; then
  echo "Falha ao criar chave. Resposta do 9Router:"
  echo "$RESP"
  echo ""
  echo "Alternativa: dashboard via túnel no PC:"
  echo "  ssh -L 20128:127.0.0.1:20128 root@$(hostname -I | awk '{print $1}')"
  echo "  http://localhost:20128/"
  exit 1
fi

echo "==> Nova chave: ${KEY:0:15}..."

grep -q '^NINEROUTER_URL=' .env || echo 'NINEROUTER_URL=http://ninerouter:20128' >> .env
if grep -q '^NINEROUTER_KEY=' .env; then
  sed -i "s|^NINEROUTER_KEY=.*|NINEROUTER_KEY=${KEY}|" .env
else
  echo "NINEROUTER_KEY=${KEY}" >> .env
fi

# Remove linhas duplicadas ou 'local'
sed -i '/^NINEROUTER_KEY=local$/d' .env

echo "==> Recriando PKF (--force-recreate recarrega .env)"
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
echo "Próximo: no dashboard 9Router conecte OpenCode Free (Providers)."
echo "  ssh -L 20128:127.0.0.1:20128 root@VPS  →  http://localhost:20128/"
