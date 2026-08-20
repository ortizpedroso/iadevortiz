#!/usr/bin/env bash
# Mescla chaves no .env da VPS sem apagar GROQ/GEMINI/NINEROUTER já configurados.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pkf}"
SECRETS_FILE="${SECRETS_FILE:-$APP_DIR/deploy/hostinger/secrets.env}"
cd "$APP_DIR"

if [ ! -f .env ]; then
  cp .env.production.example .env
fi

cp .env ".env.bak.$(date +%Y%m%d%H%M%S)"

set_kv() {
  local key="$1"
  local value="$2"
  [ -n "$value" ] || return 0
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '\n%s=%s\n' "$key" "$value" >> .env
  fi
}

# Carrega secrets locais (não versionados)
if [ -f "$SECRETS_FILE" ]; then
  # shellcheck disable=SC1090
  set -a && source "$SECRETS_FILE" && set +a
fi

# --- PKF core ---
set_kv PKF_ENV "${PKF_ENV:-production}"
set_kv PKF_HOST "${PKF_HOST:-0.0.0.0}"
set_kv PKF_PORT "${PKF_PORT:-8765}"
set_kv PKF_NO_BROWSER "${PKF_NO_BROWSER:-1}"
set_kv PKF_AUTH_TOKEN "${PKF_AUTH_TOKEN:-teste123}"
set_kv PKF_FALLBACK "${PKF_FALLBACK:-}"

set_kv PKF_PROVIDER "${PKF_PROVIDER:-ninerouter}"
set_kv PKF_PROVIDER_TIERS "${PKF_PROVIDER_TIERS:-subscription,cheap,free}"
set_kv PKF_TIER_SUBSCRIPTION "${PKF_TIER_SUBSCRIPTION:-ninerouter,kimi,groq,deepseek,openai}"
set_kv PKF_TIER_CHEAP "${PKF_TIER_CHEAP:-gemini}"
set_kv PKF_TIER_FREE "${PKF_TIER_FREE:-groq}"
set_kv PKF_PROVIDER_POOL "${PKF_PROVIDER_POOL:-ninerouter,kimi,groq,gemini,deepseek,openai}"

set_kv DATABASE_URL "${DATABASE_URL:-postgresql+asyncpg://pkf:pkf@postgres:5432/pkf}"

# --- 9Router ---
set_kv NINEROUTER_URL "${NINEROUTER_URL:-http://ninerouter:20128}"
set_kv NINEROUTER_MODEL "${NINEROUTER_MODEL:-oc/big-pickle}"
if [ -n "${NINEROUTER_KEY:-}" ]; then
  set_kv NINEROUTER_KEY "$NINEROUTER_KEY"
fi

# --- Provedores (só sobrescreve se valor não vazio) ---
[ -n "${MOONSHOT_API_KEY:-}" ] && set_kv MOONSHOT_API_KEY "$MOONSHOT_API_KEY"
set_kv KIMI_MODEL "${KIMI_MODEL:-kimi-k3}"

if [ -n "${GROQ_API_KEY:-}" ]; then
  set_kv GROQ_API_KEY "$GROQ_API_KEY"
fi
set_kv GROQ_MODEL "${GROQ_MODEL:-llama-3.1-8b-instant}"
set_kv PKF_GROQ_FALLBACK_MODEL "${PKF_GROQ_FALLBACK_MODEL:-llama-3.1-8b-instant}"

if [ -n "${GEMINI_API_KEY:-}" ]; then
  set_kv GEMINI_API_KEY "$GEMINI_API_KEY"
fi
set_kv GEMINI_MODEL "${GEMINI_MODEL:-gemini-2.0-flash}"

[ -n "${DEEPSEEK_API_KEY:-}" ] && set_kv DEEPSEEK_API_KEY "$DEEPSEEK_API_KEY"
set_kv DEEPSEEK_MODEL "${DEEPSEEK_MODEL:-deepseek-chat}"
set_kv DEEPSEEK_REASONER_MODEL "${DEEPSEEK_REASONER_MODEL:-deepseek-reasoner}"
set_kv PKF_REASONING_MODEL "${PKF_REASONING_MODEL:-deepseek-reasoner}"
set_kv PKF_REASONING_AGENTS "${PKF_REASONING_AGENTS:-architect,reviewer,logic}"
set_kv PKF_REASONING_TEMPERATURE "${PKF_REASONING_TEMPERATURE:-0.6}"
set_kv PKF_WEB_SEARCH_FORMAT "${PKF_WEB_SEARCH_FORMAT:-deepseek}"

[ -n "${OPENAI_API_KEY:-}" ] && set_kv OPENAI_API_KEY "$OPENAI_API_KEY"
set_kv OPENAI_MODEL "${OPENAI_MODEL:-gpt-5.4-mini}"

[ -n "${TAVILY_API_KEY:-}" ] && set_kv TAVILY_API_KEY "$TAVILY_API_KEY"

[ -n "${NVIDIA_API_KEY:-}" ] && set_kv NVIDIA_API_KEY "$NVIDIA_API_KEY"
set_kv NVIDIA_BASE_URL "${NVIDIA_BASE_URL:-https://integrate.api.nvidia.com/v1}"
set_kv NVIDIA_MODEL "${NVIDIA_MODEL:-meta/llama-3.3-70b-instruct}"

echo "==> .env mesclado ($(wc -l < .env) linhas)"
