#!/usr/bin/env bash
# Remove Ollama da VPS Ubuntu (serviço, binário e modelos ~5 GB)
set -euo pipefail

echo "==> Parando e desabilitando serviço Ollama"
systemctl stop ollama 2>/dev/null || true
systemctl disable ollama 2>/dev/null || true

echo "==> Removendo unit systemd"
rm -f /etc/systemd/system/ollama.service
rm -f /etc/systemd/system/default.target.wants/ollama.service
systemctl daemon-reload
systemctl reset-failed 2>/dev/null || true

echo "==> Removendo binários e bibliotecas"
rm -f /usr/local/bin/ollama
rm -rf /usr/local/lib/ollama
rm -rf /usr/share/ollama

echo "==> Removendo modelos e cache (~/.ollama)"
rm -rf /root/.ollama
for home in /home/*; do
  [ -d "$home/.ollama" ] && rm -rf "$home/.ollama"
done

echo "==> Removendo usuário/grupo ollama (se existir)"
userdel ollama 2>/dev/null || true
groupdel ollama 2>/dev/null || true

echo
echo "==> Verificação"
if command -v ollama >/dev/null 2>&1; then
  echo "AVISO: comando 'ollama' ainda encontrado: $(command -v ollama)"
else
  echo "OK: ollama removido"
fi
curl -s --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null && echo "AVISO: API :11434 ainda responde" || echo "OK: porta 11434 off"
echo
free -h
df -h /
