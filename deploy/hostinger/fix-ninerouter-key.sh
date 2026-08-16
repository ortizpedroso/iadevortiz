#!/usr/bin/env bash
# Login local no 9Router (dentro do container) + API key + recarrega PKF.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pkf}"
cd "$APP_DIR"

if ! docker compose --profile router ps ninerouter --status running -q 2>/dev/null | grep -q .; then
  echo "==> Subindo 9Router"
  docker compose --profile router up -d ninerouter
  sleep 3
fi

DASH_PASS="${NINEROUTER_DASHBOARD_PASSWORD:-123456}"
NEW_PASS="${NINEROUTER_DASHBOARD_NEW_PASSWORD:-pkf-admin-2026}"

echo "==> Login local no 9Router (loopback dentro do container)"
RESULT=$(docker compose exec -T \
  -e DASH_PASS="$DASH_PASS" \
  -e NEW_PASS="$NEW_PASS" \
  ninerouter node - <<'NODE'
const http = require("http");

const dashPass = process.env.DASH_PASS || "123456";
const newPass = process.env.NEW_PASS || "pkf-admin-2026";

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
          ...(payload ? { "Content-Length": Buffer.byteLength(payload) } : {}),
          ...(cookie ? { Cookie: cookie } : {}),
        },
      },
      (res) => {
        let text = "";
        res.on("data", (chunk) => (text += chunk));
        res.on("end", () => {
          const setCookie = res.headers["set-cookie"] || [];
          const cookieHeader = setCookie.map((part) => part.split(";")[0]).join("; ");
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
  const items = Array.isArray(data) ? data : data.keys || data.data || [];
  for (const item of items) {
    if (item && typeof item === "object") {
      const value = item.key || item.apiKey || item.api_key;
      if (value) return value;
    }
  }
  return "";
}

(async () => {
  let login = await request("POST", "/api/auth/login", { password: dashPass });
  let loginData = parseJson(login.body);

  if (!loginData.success) {
    console.log(JSON.stringify({ error: "login_failed", detail: login.body }));
    return;
  }

  let cookie = login.cookie;

  if (loginData.mustChangePassword) {
    const change = await request(
      "PATCH",
      "/api/settings",
      { currentPassword: dashPass, newPassword: newPass },
      cookie
    );
    const changeData = parseJson(change.body);
    if (change.status >= 400 && !changeData.success) {
      console.log(JSON.stringify({ error: "password_change_failed", detail: change.body }));
      return;
    }
    login = await request("POST", "/api/auth/login", { password: newPass });
    loginData = parseJson(login.body);
    cookie = login.cookie;
    if (!loginData.success) {
      console.log(JSON.stringify({ error: "login_after_change_failed", detail: login.body }));
      return;
    }
    console.error(`[info] Senha do dashboard alterada para: ${newPass}`);
  }

  let keys = await request("GET", "/api/keys", null, cookie);
  let key = extractKey(parseJson(keys.body));

  if (!key) {
    const created = await request("POST", "/api/keys", { name: "pkf-vps" }, cookie);
    key = extractKey(parseJson(created.body));
    if (!key) {
      console.log(JSON.stringify({ error: "key_create_failed", detail: created.body }));
      return;
    }
  }

  console.log(JSON.stringify({ key, dashboard_password: loginData.mustChangePassword ? newPass : dashPass }));
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
  echo "Falha:"
  echo "$RESULT"
  echo ""
  echo "Alternativa manual (PC com túnel SSH):"
  echo "  ssh -i ~/.ssh/pkf_hostinger -L 20128:127.0.0.1:20128 root@187.77.240.125"
  echo "  http://localhost:20128/dashboard/endpoint"
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
