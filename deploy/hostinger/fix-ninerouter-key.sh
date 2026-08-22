#!/usr/bin/env bash
# Login local no OmniRoute/9Router (dentro do container) + API key + recarrega PKF.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pkf}"
cd "$APP_DIR"

if ! docker compose --profile router ps ninerouter --status running -q 2>/dev/null | grep -q .; then
  echo "==> Subindo OmniRoute/9Router"
  docker compose --profile router up -d ninerouter
  sleep 5
fi

DASH_PASS="${NINEROUTER_DASHBOARD_PASSWORD:-}"
NEW_PASS="${NINEROUTER_DASHBOARD_NEW_PASSWORD:-}"
if [ -z "$NEW_PASS" ]; then
  echo "Erro: defina NINEROUTER_DASHBOARD_NEW_PASSWORD no .env (rode set-env-keys.sh)"
  exit 1
fi

echo "==> Login local no OmniRoute (loopback dentro do container)"
RESULT=$(docker compose exec -T \
  -e DASH_PASS="$DASH_PASS" \
  -e NEW_PASS="$NEW_PASS" \
  ninerouter node - <<'NODE'
const http = require("http");

const dashPass = process.env.DASH_PASS || "";
const newPass = process.env.NEW_PASS || "";

function mergeCookie(existing, incoming) {
  const jar = new Map();
  const add = (str) => {
    if (!str) return;
    for (const part of String(str).split(";")) {
      const trimmed = part.trim();
      if (!trimmed) continue;
      const eq = trimmed.indexOf("=");
      if (eq > 0) jar.set(trimmed.slice(0, eq), trimmed.slice(eq + 1));
    }
  };
  add(existing);
  add(incoming);
  return Array.from(jar.entries())
    .map(([key, value]) => `${key}=${value}`)
    .join("; ");
}

function request(method, path, body, cookie) {
  return new Promise((resolve, reject) => {
    const payload = body ? JSON.stringify(body) : null;
    const req = http.request(
      {
        hostname: "127.0.0.1",
        port: 20128,
        path,
        method,
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          ...(payload ? { "Content-Length": Buffer.byteLength(payload) } : {}),
          ...(cookie ? { Cookie: cookie } : {}),
        },
      },
      (res) => {
        let text = "";
        res.on("data", (chunk) => (text += chunk));
        res.on("end", () => {
          const setCookie = res.headers["set-cookie"] || [];
          const cookieHeader = Array.isArray(setCookie)
            ? setCookie.map((part) => part.split(";")[0]).join("; ")
            : String(setCookie).split(";")[0];
          resolve({ status: res.statusCode, body: text, cookie: cookieHeader });
        });
      }
    );
    req.on("error", reject);
    if (payload) req.write(payload);
    req.end();
  });
}

function parseJson(text) {
  try {
    return JSON.parse(text || "{}");
  } catch {
    return {};
  }
}

function extractKey(data) {
  if (!data) return "";
  if (typeof data === "string") return "";
  if (data.key) return data.key;
  if (data.apiKey) return data.apiKey;
  if (data.api_key) return data.api_key;
  const items = Array.isArray(data) ? data : data.keys || data.data || data.items || [];
  for (const item of items) {
    if (!item || typeof item !== "object") continue;
    const value = item.key || item.apiKey || item.api_key || item.plaintextKey;
    if (value) return value;
  }
  return "";
}

(async () => {
  let cookieJar = "";
  const bootstrap = await request("GET", "/api/settings/require-login", null, cookieJar);
  cookieJar = mergeCookie(cookieJar, bootstrap.cookie);
  const bootstrapData = parseJson(bootstrap.body);

  async function tryLogin(password) {
    const attempt = await request("POST", "/api/auth/login", { password }, cookieJar);
    cookieJar = mergeCookie(cookieJar, attempt.cookie);
    const data = parseJson(attempt.body);
    return { attempt, data };
  }

  const passwordCandidates = [...new Set(
    [
      newPass,
      dashPass,
      process.env.ALLOW_LEGACY_OMNI_PASSWORD === "1" ? "pkf-admin-2026" : "",
      process.env.ALLOW_LEGACY_OMNI_PASSWORD === "1" ? "123456" : "",
    ].filter(Boolean)
  )];
  let activePass = passwordCandidates[0];
  let login = await tryLogin(activePass);
  let loginData = login.data;

  if (!loginData.success) {
    const loginErr = parseJson(login.body);
    const needsSetup =
      loginErr.needsSetup === true ||
      bootstrapData.hasPassword === false ||
      String(loginErr.error || "").toLowerCase().includes("onboarding");

    if (needsSetup) {
      const setup = await request(
        "POST",
        "/api/settings/require-login",
        { requireLogin: true, password: newPass },
        cookieJar
      );
      cookieJar = mergeCookie(cookieJar, setup.cookie);
      const setupData = parseJson(setup.body);
      if (!setupData.success) {
        console.log(JSON.stringify({ error: "setup_failed", detail: setup.body }));
        return;
      }
      console.error("[info] OmniRoute onboarding: senha inicial definida");
      activePass = newPass;
      login = await tryLogin(activePass);
      loginData = login.data;
    } else {
      for (const candidate of passwordCandidates.slice(1)) {
        login = await tryLogin(candidate);
        loginData = login.data;
        if (loginData.success) {
          activePass = candidate;
          break;
        }
      }
    }
  }

  if (!loginData.success) {
    console.log(JSON.stringify({ error: "login_failed", detail: login.body }));
    return;
  }

  if (loginData.mustChangePassword) {
    const change = await request(
      "PATCH",
      "/api/settings",
      { currentPassword: activePass, newPassword: newPass },
      cookieJar
    );
    cookieJar = mergeCookie(cookieJar, change.cookie);
    const changeData = parseJson(change.body);
    if (change.status >= 400 && !changeData.success) {
      console.log(JSON.stringify({ error: "password_change_failed", detail: change.body }));
      return;
    }
    login = await tryLogin(newPass);
    loginData = login.data;
    if (!loginData.success) {
      console.log(JSON.stringify({ error: "login_after_change_failed", detail: login.body }));
      return;
    }
    activePass = newPass;
    console.error("[info] Senha do dashboard alterada");
  }

  let keys = await request("GET", "/api/keys", null, cookieJar);
  cookieJar = mergeCookie(cookieJar, keys.cookie);
  let key = extractKey(parseJson(keys.body));

  if (!key) {
    const created = await request("POST", "/api/keys", { name: "pkf-vps" }, cookieJar);
    cookieJar = mergeCookie(cookieJar, created.cookie);
    key = extractKey(parseJson(created.body));
    if (!key) {
      console.log(JSON.stringify({ error: "key_create_failed", detail: created.body, cookie: cookieJar ? "set" : "empty" }));
      return;
    }
  }

  console.log(JSON.stringify({ key, dashboard_password: activePass }));
})().catch((err) => {
  console.log(JSON.stringify({ error: "exception", detail: String(err) }));
});
NODE
)

KEY=$(python3 - <<'PY' "$RESULT"
import json, sys
try:
    data = json.loads(sys.argv[1])
except json.JSONDecodeError:
    print("")
    sys.exit(0)
print(data.get("key") or "")
PY
)

if [ -z "$KEY" ]; then
  echo "Falha no dashboard OmniRoute:"
  echo "$RESULT"
  echo ""
  echo "Execute na VPS: bash deploy/hostinger/update.sh"
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

for _ in $(seq 1 20); do
  curl -sf http://127.0.0.1:8765/api/health >/dev/null 2>&1 && break
  sleep 2
done

echo "==> Resultado"
PKF_TOKEN="$(grep '^PKF_AUTH_TOKEN=' .env 2>/dev/null | tail -n1 | cut -d= -f2-)"
python3 - <<PY
import json, urllib.request
token = "${PKF_TOKEN}"
url = "http://127.0.0.1:8765/api/health"
if token:
    url += f"?token={token}"
try:
    data = json.load(urllib.request.urlopen(url, timeout=8))
    print("ninerouter_ok:", data.get("ninerouter_ok"))
    if data.get("ninerouter_error"):
        print("ninerouter_error:", data.get("ninerouter_error"))
except Exception as exc:
    print("health check falhou:", exc)
PY
