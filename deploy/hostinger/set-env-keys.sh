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

set_kv_default() {
  local key="$1"
  local value="$2"
  grep -q "^${key}=" .env || set_kv "$key" "$value"
}

migrate_openai_model() {
  local current=""
  if grep -q "^OPENAI_MODEL=" .env; then
    current="$(grep "^OPENAI_MODEL=" .env | head -n1 | cut -d= -f2-)"
  fi
  case "$current" in
    gpt-5.4-mini|gpt-4.1-mini|gpt-4.1-mini-*|"")
      set_kv OPENAI_MODEL "gpt-4o-mini"
      ;;
  esac
}

migrate_gemini_model() {
  local current=""
  if grep -q "^GEMINI_MODEL=" .env; then
    current="$(grep "^GEMINI_MODEL=" .env | head -n1 | cut -d= -f2-)"
  fi
  case "$current" in
    gemini-2.0-flash|gemini-2.0-flash-*|gemini-1.5-*|"")
      set_kv GEMINI_MODEL "gemini-2.5-flash"
      echo "==> GEMINI_MODEL migrado para gemini-2.5-flash (gemini-2.0-flash descontinuado)"
      ;;
  esac
}

migrate_provider_pool() {
  local current=""
  if grep -q "^PKF_PROVIDER_POOL=" .env; then
    current="$(grep "^PKF_PROVIDER_POOL=" .env | head -n1 | cut -d= -f2-)"
  fi
  if [ "${PKF_ROUTER_ONLY:-1}" = "1" ]; then
    case "$current" in
      ninerouter|"") ;;
      *)
        set_kv PKF_PROVIDER_POOL "ninerouter"
        set_kv PKF_PROVIDER "ninerouter"
        set_kv PKF_TIER_SUBSCRIPTION "ninerouter"
        set_kv PKF_TIER_CHEAP "ninerouter"
        set_kv PKF_TIER_FREE "ninerouter"
        echo "==> Pool migrado para router-only (OmniRoute): ninerouter"
        ;;
    esac
    return 0
  fi
  case "$current" in
    gemini-only|gemini)
      set_kv PKF_PROVIDER_POOL "ninerouter,kimi,groq,gemini,deepseek"
      set_kv PKF_PROVIDER "ninerouter"
      echo "==> Pool migrado de '${current}' para incluir 9Router/Groq"
      ;;
    openai,gemini|openai|openai,*|*,openai)
      if [ "${OPENAI_IN_POOL:-0}" != "1" ]; then
        set_kv PKF_PROVIDER_POOL "ninerouter,kimi,groq,gemini,deepseek"
        echo "==> Pool migrado de '${current}' (OpenAI removido; use OPENAI_IN_POOL=1 para reativar)"
      fi
      ;;
  esac
  if grep -q "^PKF_PROVIDER=openai" .env && [ "${PKF_PROVIDER:-}" != "openai" ]; then
    set_kv PKF_PROVIDER "ninerouter"
    echo "==> PKF_PROVIDER migrado de openai para ninerouter"
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
if ! grep -q '^PKF_AUTH_TOKEN=' .env; then
  _auth="${PKF_AUTH_TOKEN:-}"
  if [ -z "$_auth" ] && [ "${PKF_ENV:-production}" = "production" ]; then
    _auth="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))' 2>/dev/null || openssl rand -hex 24)"
    echo "==> PKF_AUTH_TOKEN gerado automaticamente na primeira instalação"
  fi
  set_kv PKF_AUTH_TOKEN "${_auth}"
fi

dedupe_env_key() {
  local key="$1"
  if [ "$(grep -c "^${key}=" .env 2>/dev/null || echo 0)" -le 1 ]; then
    return 0
  fi
  local value=""
  value="$(grep "^${key}=" .env | tail -n1 | cut -d= -f2-)"
  grep -v "^${key}=" .env > .env.tmp
  printf '%s=%s\n' "$key" "$value" >> .env.tmp
  mv .env.tmp .env
  echo "==> Removida duplicata de ${key} no .env"
}

dedupe_env_key PKF_AUTH_TOKEN
dedupe_env_key NINEROUTER_KEY

migrate_weak_auth_token() {
  if [ "${PKF_ENV:-production}" != "production" ]; then
    return 0
  fi
  local current=""
  current="$(grep '^PKF_AUTH_TOKEN=' .env 2>/dev/null | tail -n1 | cut -d= -f2- || true)"
  [ -n "$current" ] || return 0
  local weak=0
  case "${current,,}" in
    teste123|changeme|password|pkf) weak=1 ;;
  esac
  if [ "${#current}" -lt 16 ]; then
    weak=1
  fi
  if [ "$weak" -eq 0 ]; then
    return 0
  fi
  local new_token=""
  new_token="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))' 2>/dev/null || openssl rand -hex 24)"
  set_kv PKF_AUTH_TOKEN "$new_token"
  echo "==> PKF_AUTH_TOKEN fraco/padrão migrado automaticamente (produção exige token forte)"
  echo "==> Leia o novo valor localmente: grep '^PKF_AUTH_TOKEN=' .env"
}

migrate_weak_auth_token

migrate_omniroute_password() {
  local current=""
  current="$(grep '^NINEROUTER_DASHBOARD_NEW_PASSWORD=' .env 2>/dev/null | tail -n1 | cut -d= -f2- || true)"
  case "${current,,}" in
    pkf-admin-2026|123456) ;;
    "")
      if docker volume ls 2>/dev/null | grep -Eq 'omniroute-data|pkf_omniroute-data'; then
        echo "==> OmniRoute: volume existente — mantendo senha persistida (não gera nova no .env)"
        return 0
      fi
      ;;
    *)
      if [ "${#current}" -ge 12 ]; then
        return 0
      fi
      ;;
  esac
  local new_pass=""
  new_pass="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))' 2>/dev/null || openssl rand -hex 16)"
  set_kv NINEROUTER_DASHBOARD_NEW_PASSWORD "$new_pass"
  echo "==> NINEROUTER_DASHBOARD_NEW_PASSWORD fraco/ausente — gerado automaticamente"
  echo "==> Leia localmente: grep '^NINEROUTER_DASHBOARD_NEW_PASSWORD=' .env"
}

migrate_postgres_password() {
  sync_database_url() {
    local pg_pass=""
    pg_pass="$(grep '^POSTGRES_PASSWORD=' .env 2>/dev/null | tail -n1 | cut -d= -f2- || echo pkf)"
    set_kv DATABASE_URL "postgresql+asyncpg://pkf:${pg_pass}@postgres:5432/pkf"
  }

  if grep -q '^POSTGRES_PASSWORD=' .env; then
    sync_database_url
    return 0
  fi

  if docker volume ls 2>/dev/null | grep -Eq 'pkf-postgres|pkf_pkf-postgres'; then
    set_kv POSTGRES_PASSWORD "pkf"
    echo "==> POSTGRES_PASSWORD=pkf (volume Postgres existente — compatibilidade)"
    sync_database_url
    return 0
  fi

  local pass=""
  pass="$(python3 -c 'import secrets; print(secrets.token_urlsafe(16))' 2>/dev/null || openssl rand -hex 16)"
  set_kv POSTGRES_PASSWORD "$pass"
  echo "==> POSTGRES_PASSWORD gerado automaticamente (instalação nova)"
  sync_database_url
}

repair_postgres_env_if_needed() {
  if ! docker volume ls 2>/dev/null | grep -Eq 'pkf-postgres|pkf_pkf-postgres'; then
    return 0
  fi
  local current=""
  current="$(grep '^POSTGRES_PASSWORD=' .env 2>/dev/null | tail -n1 | cut -d= -f2- || true)"
  if [ "$current" = "pkf" ]; then
    return 0
  fi
  echo "==> Reparando POSTGRES_PASSWORD/DATABASE_URL para volume legacy (pkf)"
  set_kv POSTGRES_PASSWORD "pkf"
  set_kv DATABASE_URL "postgresql+asyncpg://pkf:pkf@postgres:5432/pkf"
}

migrate_omniroute_password
migrate_postgres_password
repair_postgres_env_if_needed

sync_database_url() {
  local pg_pass=""
  pg_pass="$(grep '^POSTGRES_PASSWORD=' .env 2>/dev/null | tail -n1 | cut -d= -f2- || echo pkf)"
  set_kv DATABASE_URL "postgresql+asyncpg://pkf:${pg_pass}@postgres:5432/pkf"
}
sync_database_url
set_kv PKF_FALLBACK "${PKF_FALLBACK:-}"

set_kv PKF_PROVIDER "${PKF_PROVIDER:-ninerouter}"
set_kv PKF_ROUTER_ONLY "${PKF_ROUTER_ONLY:-1}"
set_kv ROUTER_IMAGE "${ROUTER_IMAGE:-diegosouzapw/omniroute:latest}"
set_kv PKF_PROVIDER_TIERS "${PKF_PROVIDER_TIERS:-subscription,cheap,free}"
# Modo router-only: só OmniRoute/9Router — provedores configurados no dashboard do gateway.
if [ "${PKF_ROUTER_ONLY:-1}" = "1" ]; then
  _pool_default="ninerouter"
  _tier_sub="ninerouter"
  _tier_cheap="ninerouter"
  _tier_free="ninerouter"
else
  _pool_default="ninerouter,kimi,groq,gemini,deepseek"
  if [ "${OPENAI_IN_POOL:-0}" = "1" ] && [ -n "${OPENAI_API_KEY:-}" ]; then
    _pool_default="${_pool_default},openai"
  fi
  _tier_sub="ninerouter,kimi,groq,deepseek"
  _tier_cheap="gemini"
  _tier_free="groq"
fi
set_kv PKF_TIER_SUBSCRIPTION "${PKF_TIER_SUBSCRIPTION:-${_tier_sub}}"
set_kv PKF_TIER_CHEAP "${PKF_TIER_CHEAP:-${_tier_cheap}}"
set_kv PKF_TIER_FREE "${PKF_TIER_FREE:-${_tier_free}}"
set_kv PKF_PROVIDER_POOL "${PKF_PROVIDER_POOL:-${_pool_default}}"
migrate_provider_pool

set_kv DATABASE_URL "${DATABASE_URL:-postgresql+asyncpg://pkf:${POSTGRES_PASSWORD:-pkf}@postgres:5432/pkf}"

# --- 9Router ---
set_kv NINEROUTER_URL "${NINEROUTER_URL:-http://ninerouter:20128}"
set_kv_default NINEROUTER_MODEL "${NINEROUTER_MODEL:-auto/free}"
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
set_kv GEMINI_MODEL "${GEMINI_MODEL:-gemini-2.5-flash}"
migrate_gemini_model

[ -n "${DEEPSEEK_API_KEY:-}" ] && set_kv DEEPSEEK_API_KEY "$DEEPSEEK_API_KEY"
set_kv DEEPSEEK_MODEL "${DEEPSEEK_MODEL:-deepseek-chat}"
set_kv DEEPSEEK_REASONER_MODEL "${DEEPSEEK_REASONER_MODEL:-deepseek-reasoner}"
set_kv PKF_REASONING_MODEL "${PKF_REASONING_MODEL:-deepseek-reasoner}"
set_kv PKF_REASONING_AGENTS "${PKF_REASONING_AGENTS:-architect,reviewer,logic}"
set_kv PKF_REASONING_TEMPERATURE "${PKF_REASONING_TEMPERATURE:-0.6}"
set_kv PKF_WEB_SEARCH_FORMAT "${PKF_WEB_SEARCH_FORMAT:-deepseek}"

[ -n "${OPENAI_API_KEY:-}" ] && set_kv OPENAI_API_KEY "$OPENAI_API_KEY"
migrate_openai_model
set_kv_default OPENAI_MODEL "gpt-4o-mini"

[ -n "${TAVILY_API_KEY:-}" ] && set_kv TAVILY_API_KEY "$TAVILY_API_KEY"

[ -n "${NVIDIA_API_KEY:-}" ] && set_kv NVIDIA_API_KEY "$NVIDIA_API_KEY"
set_kv NVIDIA_BASE_URL "${NVIDIA_BASE_URL:-https://integrate.api.nvidia.com/v1}"
set_kv NVIDIA_MODEL "${NVIDIA_MODEL:-meta/llama-3.3-70b-instruct}"

strip_direct_keys_router_only() {
  if [ "${PKF_ROUTER_ONLY:-1}" != "1" ]; then
    return 0
  fi
  local key
  for key in GROQ_API_KEY GROQ_API_KEY_2 GEMINI_API_KEY GOOGLE_API_KEY MOONSHOT_API_KEY OPENAI_API_KEY DEEPSEEK_API_KEY MIMO_API_KEY NVIDIA_API_KEY; do
    if grep -q "^${key}=" .env 2>/dev/null; then
      sed -i "s|^${key}=|# ${key}= (desativado em PKF_ROUTER_ONLY=1)|" .env
    fi
  done
  echo "==> Chaves diretas comentadas (router-only usa só OmniRoute)"
}

strip_direct_keys_router_only
