#!/usr/bin/env bash
# Diagnóstico PKF + 9Router + Docker na VPS
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pkf}"
cd "$APP_DIR"

echo "========== DOCKER COMPOSE =========="
docker compose --profile router ps || true

echo ""
echo "========== PORTAS (8765 PKF, 20128 9Router) =========="
ss -tlnp | grep -E ':8765|:20128' || echo "(nenhuma porta encontrada)"

echo ""
echo "========== 9ROUTER (host → 127.0.0.1:20128) =========="
curl -s -o /dev/null -w "HTTP %{http_code}\n" --max-time 5 http://127.0.0.1:20128/ || echo "FALHOU"

echo ""
echo "========== 9ROUTER (dentro do container) =========="
docker compose exec -T ninerouter node -e "require('http').get('http://127.0.0.1:20128/',r=>{console.log('HTTP',r.statusCode);process.exit(0)}).on('error',e=>{console.error(e.message);process.exit(1)})" 2>/dev/null || echo "container ninerouter inacessível"

echo ""
echo "========== PKF /api/health =========="
curl -s --max-time 8 http://127.0.0.1:8765/api/health | python3 -m json.tool 2>/dev/null || curl -s --max-time 8 http://127.0.0.1:8765/api/health || echo "PKF não responde"

echo ""
echo "========== .env NINEROUTER =========="
grep -E '^NINEROUTER|^PKF_PROVIDER=' .env 2>/dev/null | sed 's/sk-.*/sk-***/' || echo "(sem .env)"

echo ""
echo "========== PKF container env =========="
docker compose exec -T pkf printenv 2>/dev/null | grep -E '^NINEROUTER|^PKF_PROVIDER' | sed 's/sk-.*/sk-***/' || true

echo ""
echo "========== LOGS (últimas 5 linhas) =========="
echo "--- ninerouter ---"
docker compose logs --tail 5 ninerouter 2>/dev/null || true
echo "--- pkf ---"
docker compose logs --tail 5 pkf 2>/dev/null || true

echo ""
echo "========== Ações sugeridas =========="
echo "Se ninerouter parado:  docker compose --profile router up -d ninerouter"
echo "Se pkf parado:         docker compose --profile router up -d pkf"
echo "Corrigir API key:      bash deploy/hostinger/fix-ninerouter-key.sh"
echo "PKF externo:           http://$(curl -s ifconfig.me 2>/dev/null || echo IP):8765/?token=SEU_TOKEN"
echo "Dashboard 9Router:     no PC: ssh -L 20128:127.0.0.1:20128 root@VPS  →  http://localhost:20128/"
