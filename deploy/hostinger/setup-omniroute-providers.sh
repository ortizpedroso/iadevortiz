#!/usr/bin/env bash
# Configura provedores free no OmniRoute/9Router automaticamente (sem dashboard).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pkf}"
cd "$APP_DIR"

if ! docker compose --profile router ps ninerouter --status running -q 2>/dev/null | grep -q .; then
  docker compose --profile router up -d ninerouter
  sleep 5
fi

DASH_PASS="${NINEROUTER_DASHBOARD_NEW_PASSWORD:-pkf-admin-2026}"

echo "==> OmniRoute: provedores free automáticos"
RESULT=$(docker compose exec -T \
  -e DASH_PASS="$DASH_PASS" \
  -e NEW_PASS="$DASH_PASS" \
  ninerouter node - <<'NODE'
const http = require("http");

const dashPass = process.env.DASH_PASS || "pkf-admin-2026";
const newPass = process.env.NEW_PASS || dashPass;

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
  return Array.from(jar.entries()).map(([k, v]) => `${k}=${v}`).join("; ");
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

const FREE_PROVIDERS = [
  { provider: "open-code", name: "pkf-opencode-free" },
  { provider: "pollinations", name: "pkf-pollinations" },
  { provider: "cloudflare-ai", name: "pkf-cloudflare" },
];

(async () => {
  let cookieJar = "";
  const bootstrap = await request("GET", "/api/settings/require-login", null, cookieJar);
  cookieJar = mergeCookie(cookieJar, bootstrap.cookie);

  async function tryLogin(password) {
    const attempt = await request("POST", "/api/auth/login", { password }, cookieJar);
    cookieJar = mergeCookie(cookieJar, attempt.cookie);
    return parseJson(attempt.body);
  }

  const candidates = [...new Set([newPass, dashPass, "pkf-admin-2026", "123456"])];
  let loginData = { success: false };
  for (const password of candidates) {
    loginData = await tryLogin(password);
    if (loginData.success) break;
  }

  if (!loginData.success) {
    const setup = await request(
      "POST",
      "/api/settings/require-login",
      { requireLogin: true, password: newPass },
      cookieJar
    );
    cookieJar = mergeCookie(cookieJar, setup.cookie);
    loginData = await tryLogin(newPass);
  }

  if (!loginData.success) {
    console.log(JSON.stringify({ ok: false, error: "login_failed" }));
    return;
  }

  let list = await request("GET", "/api/providers", null, cookieJar);
  cookieJar = mergeCookie(cookieJar, list.cookie);
  const existing = parseJson(list.body);
  const items = Array.isArray(existing) ? existing : existing.providers || existing.data || [];
  const connected = new Set(
    items.map((item) => String(item.provider || item.type || "").toLowerCase()).filter(Boolean)
  );

  const added = [];
  for (const spec of FREE_PROVIDERS) {
    if (connected.has(spec.provider)) continue;
    const created = await request(
      "POST",
      "/api/providers",
      { provider: spec.provider, name: spec.name },
      cookieJar
    );
    cookieJar = mergeCookie(cookieJar, created.cookie);
    const data = parseJson(created.body);
    if (created.status < 400 || data.success || data.id) {
      added.push(spec.provider);
      connected.add(spec.provider);
    }
  }

  console.log(JSON.stringify({ ok: true, added, connected: [...connected] }));
})().catch((err) => {
  console.log(JSON.stringify({ ok: false, error: String(err) }));
});
NODE
)

echo "$RESULT" | python3 -m json.tool 2>/dev/null || echo "$RESULT"

grep -q '^NINEROUTER_MODEL=' .env || echo 'NINEROUTER_MODEL=oc/big-pickle' >> .env
grep -q '^PKF_NINEROUTER_MODEL_CHAIN=' .env || cat >> .env <<'EOF'
PKF_NINEROUTER_MODEL_CHAIN=oc/big-pickle,auto/coding,auto,auto/free
EOF

echo "==> NINEROUTER_MODEL=oc/big-pickle (padrão estável; auto/free só na cadeia de fallback)"
