#!/usr/bin/env bash
# Diagnóstico rápido da VPS — Ollama, Docker, PKF, recursos
set -u

section() { echo; echo "========== $1 =========="; }

section "SISTEMA"
echo "Host: $(hostname)"
echo "OS:   $(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME" || uname -a)"
echo "Uptime: $(uptime -p 2>/dev/null || uptime)"
echo "User: $(whoami)"

section "RECURSOS"
if command -v free >/dev/null 2>&1; then
  free -h
else
  echo "free não disponível"
fi
echo "--- Disco ---"
df -h / /opt 2>/dev/null || df -h /
echo "--- CPU ---"
nproc 2>/dev/null || echo "nproc indisponível"
command -v lscpu >/dev/null 2>&1 && lscpu | grep -E "Model name|CPU\(s\)|Architecture" || true

section "REDE / PORTAS"
echo "IP público (se curl ok): $(curl -s --max-time 3 ifconfig.me 2>/dev/null || echo 'indisponível')"
for port in 22 80 443 8765 11434; do
  if command -v ss >/dev/null 2>&1; then
    ss -tlnp 2>/dev/null | grep ":$port " && echo "  ^ porta $port em uso" || echo "  porta $port: livre"
  elif command -v netstat >/dev/null 2>&1; then
    netstat -tlnp 2>/dev/null | grep ":$port " || echo "  porta $port: livre"
  fi
done

section "OLLAMA"
if command -v ollama >/dev/null 2>&1; then
  echo "Binário: $(command -v ollama)"
  ollama --version 2>/dev/null || true
  if curl -s --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "Serviço: RODANDO em :11434"
    echo "Modelos instalados:"
    ollama list 2>/dev/null || curl -s http://127.0.0.1:11434/api/tags | head -c 500
  else
    echo "Serviço: INSTALADO mas NÃO responde em :11434"
    echo "Tente: sudo systemctl status ollama  (ou abra o app Ollama)"
  fi
else
  echo "Ollama: NÃO instalado no PATH"
fi
if systemctl is-active ollama >/dev/null 2>&1; then
  echo "systemd ollama: $(systemctl is-active ollama)"
  systemctl status ollama --no-pager -l 2>/dev/null | head -5
fi

section "DOCKER"
if command -v docker >/dev/null 2>&1; then
  docker --version
  docker compose version 2>/dev/null || docker-compose --version 2>/dev/null || echo "Compose: não encontrado"
  echo "--- Containers ---"
  docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
  echo "--- Imagens ---"
  docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" 2>/dev/null | head -15
else
  echo "Docker: NÃO instalado"
fi

section "PKF"
for dir in /opt/pkf "$HOME/pkf" "$(pwd)"; do
  if [ -f "$dir/docker-compose.yml" ] || [ -d "$dir/pkf" ]; then
    echo "Encontrado em: $dir"
    [ -f "$dir/.env" ] && echo "  .env: existe" || echo "  .env: ausente"
    [ -f "$dir/docker-compose.yml" ] && echo "  docker-compose.yml: sim"
    if [ -f "$dir/.env" ]; then
      grep -E "^PKF_|^MOONSHOT|^OPENAI|^OLLAMA" "$dir/.env" 2>/dev/null | sed 's/=.*/=***/' || true
    fi
  fi
done
if curl -s --max-time 2 http://127.0.0.1:8765/api/health >/dev/null 2>&1; then
  echo "PKF UI: respondendo em :8765"
  curl -s http://127.0.0.1:8765/api/health
elif curl -s --max-time 2 http://127.0.0.1:80/api/health >/dev/null 2>&1; then
  echo "PKF UI: respondendo em :80 (nginx)"
  curl -s http://127.0.0.1:80/api/health
else
  echo "PKF UI: não detectada nas portas 8765/80"
fi

section "PYTHON / GIT"
command -v python3 >/dev/null 2>&1 && python3 --version || echo "python3: não"
command -v git >/dev/null 2>&1 && git --version || echo "git: não"

section "FIREWALL"
if command -v ufw >/dev/null 2>&1; then
  sudo ufw status 2>/dev/null || ufw status 2>/dev/null || true
elif command -v firewall-cmd >/dev/null 2>&1; then
  sudo firewall-cmd --list-all 2>/dev/null || true
else
  echo "ufw/firewalld não encontrado"
fi

section "RECOMENDAÇÃO"
RAM_MB=$(free -m 2>/dev/null | awk '/Mem:/ {print $2}')
if [ -n "${RAM_MB:-}" ] && [ "$RAM_MB" -lt 6000 ] 2>/dev/null; then
  echo "RAM ~${RAM_MB}MB — evite Ollama com llama3:8b (precisa ~8GB). Use Kimi/OpenAI na PKF."
else
  echo "RAM ok para app leve. Ollama local só se tiver 8GB+ livres."
fi
echo "Próximo passo PKF: cd /opt/pkf && cp .env.production.example .env && bash deploy/hostinger/setup.sh"
echo "Diagnóstico concluído."
