#!/usr/bin/env bash
# Testa WebSocket da PKF na VPS.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pkf}"
cd "$APP_DIR"

TOKEN="$(grep '^PKF_AUTH_TOKEN=' .env 2>/dev/null | tail -n1 | cut -d= -f2-)"
if [ -z "$TOKEN" ]; then
  echo "Erro: PKF_AUTH_TOKEN ausente no .env"
  exit 1
fi

echo "==> HTTP health"
curl -sf -H "Authorization: Bearer ${TOKEN}" "http://127.0.0.1:8765/api/health" | python3 -m json.tool | head -20

echo ""
echo "==> WebSocket (python, subprotocol)"
docker compose exec -T -e "WS_TOKEN=${TOKEN}" pkf python3 - <<'PY'
import asyncio
import json
import os

try:
    import websockets
except ImportError:
    print("websockets não instalado — instale com: pip install websockets")
    raise SystemExit(1)

TOKEN = os.environ.get("WS_TOKEN", "")

async def main() -> None:
    uri = "ws://127.0.0.1:8765/ws"
    async with websockets.connect(
        uri,
        subprotocols=[f"pkf-token.{TOKEN}"],
        open_timeout=8,
    ) as ws:
        raw = await asyncio.wait_for(ws.recv(), timeout=8)
        data = json.loads(raw)
        print("ws_ok:", data.get("type") == "session")
        print("provider:", data.get("provider"))

asyncio.run(main())
PY
