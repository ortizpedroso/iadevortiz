#!/usr/bin/env bash
# Liga o PKF à rede do Caddy do eventosbr e acrescenta o site em PKF_HOST_DOMAIN.
# Não altera o bloco de www.eventosbr.app.br nem o bloco Métrica / SIGEP.
set -euo pipefail

CADDY_CTR="${CADDY_CTR:-eventosbr-caddy-1}"
WEB_CTR="${WEB_CTR:-pkf-pkf-1}"
HOST="${PKF_HOST_DOMAIN:-}"

if [[ -z "$HOST" ]]; then
  echo "Erro: defina PKF_HOST_DOMAIN antes de rodar este hook."
  exit 1
fi

if ! docker inspect "$CADDY_CTR" >/dev/null 2>&1; then
  echo "Container $CADDY_CTR não encontrado. Ajuste CADDY_CTR=..."
  docker ps --format '{{.Names}} {{.Image}} {{.Ports}}'
  exit 1
fi

if ! docker inspect "$WEB_CTR" >/dev/null 2>&1; then
  echo "Container $WEB_CTR não encontrado. Suba a stack do PKF primeiro."
  exit 1
fi

NET="$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}' "$CADDY_CTR" | awk 'NF{print; exit}')"
if [[ -z "$NET" ]]; then
  echo "Não achei a Docker network do Caddy."
  exit 1
fi

echo "Rede do Caddy: $NET"
docker network connect "$NET" "$WEB_CTR" 2>/dev/null || echo "web já está na rede $NET"

CADDYFILE_HOST="$(
  docker inspect -f '{{range .Mounts}}{{if eq .Destination "/etc/caddy/Caddyfile"}}{{.Source}}{{end}}{{end}}' "$CADDY_CTR"
)"
if [[ -z "$CADDYFILE_HOST" || ! -f "$CADDYFILE_HOST" ]]; then
  echo "Não achei o Caddyfile montado em /etc/caddy/Caddyfile."
  exit 1
fi

echo "Caddyfile: $CADDYFILE_HOST"

python3 - "$CADDYFILE_HOST" "$HOST" "$WEB_CTR" <<'PY'
from pathlib import Path
import sys

path, host, web = sys.argv[1], sys.argv[2], sys.argv[3]
text = Path(path).read_text()
# reverse_proxy do Caddy 2 faz upgrade WebSocket automaticamente (sem headers manuais).
block = (
    f"\n# PKF — não remover o bloco do eventosbr\n"
    f"{host} {{\n"
    f"\tencode gzip zstd\n"
    f"\treverse_proxy {web}:8765\n"
    f"}}\n"
)
marker = "# PKF —"
if marker in text:
    start = text.index(marker)
    rest = text[start:]
    brace = rest.find("}")
    if brace == -1:
        raise SystemExit("bloco PKF no Caddyfile sem '}'")
    text = text[:start] + block.lstrip("\n") + rest[brace + 1 :]
elif host in text:
    lines = text.splitlines(keepends=True)
    out = []
    in_host = False
    replaced = False
    for line in lines:
        if host in line and "{" in line:
            in_host = True
        if in_host and "reverse_proxy" in line:
            indent = line[: len(line) - len(line.lstrip())]
            line = f"{indent}reverse_proxy {web}:8765\n"
            replaced = True
            in_host = False
        out.append(line)
    text = "".join(out)
    if not replaced:
        text += block
else:
    text += block
Path(path).write_text(text)
print(f"Caddyfile atualizado: {host} -> {web}:8765")
PY

docker exec "$CADDY_CTR" caddy reload --config /etc/caddy/Caddyfile
echo
echo "Teste: curl -sI https://$HOST | head"
