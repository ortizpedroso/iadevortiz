#!/usr/bin/env bash
# Adiciona NVIDIA NIM ao 9Router (dashboard local) e grava NVIDIA_API_KEY no secrets.env.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pkf}"
SECRETS_FILE="${SECRETS_FILE:-$APP_DIR/deploy/hostinger/secrets.env}"
DASH_PASS="${NINEROUTER_DASHBOARD_PASSWORD:-SuaSenhaNova2026!}"
NVIDIA_KEY="${NVIDIA_API_KEY:-}"

if [ -z "$NVIDIA_KEY" ]; then
  if [ -f "$SECRETS_FILE" ]; then
    # shellcheck disable=SC1090
    set -a && source "$SECRETS_FILE" && set +a
    NVIDIA_KEY="${NVIDIA_API_KEY:-}"
  fi
fi

if [ -z "$NVIDIA_KEY" ]; then
  echo "Defina NVIDIA_API_KEY ou coloque em $SECRETS_FILE"
  exit 1
fi

cd "$APP_DIR"
mkdir -p deploy/hostinger
touch "$SECRETS_FILE"
chmod 600 "$SECRETS_FILE"
if grep -q '^NVIDIA_API_KEY=' "$SECRETS_FILE"; then
  sed -i "s|^NVIDIA_API_KEY=.*|NVIDIA_API_KEY=${NVIDIA_KEY}|" "$SECRETS_FILE"
else
  printf '\nNVIDIA_API_KEY=%s\n' "$NVIDIA_KEY" >> "$SECRETS_FILE"
fi

if ! docker compose --profile router ps ninerouter --status running -q 2>/dev/null | grep -q .; then
  docker compose --profile router up -d ninerouter
  sleep 3
fi

echo "==> Validando chave NVIDIA + registrando no 9Router"
docker compose exec -T \
  -e DASH_PASS="$DASH_PASS" \
  -e NVIDIA_KEY="$NVIDIA_KEY" \
  ninerouter node - <<'NODE'
const http = require("http");

const dashPass = process.env.DASH_PASS || "";
const nvidiaKey = process.env.NVIDIA_KEY || "";

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

(async () => {
  const login = await request("POST", "/api/auth/login", { password: dashPass });
  const loginData = parseJson(login.body);
  if (!loginData.success) {
    console.log(JSON.stringify({ error: "login_failed", detail: login.body }));
    return;
  }
  const cookie = login.cookie;

  const validate = await request(
    "POST",
    "/api/providers/validate",
    { provider: "nvidia", apiKey: nvidiaKey, name: "pkf-nvidia" },
    cookie
  );
  const validateData = parseJson(validate.body);
  if (validate.status >= 400 && !validateData.valid && !validateData.success) {
    console.log(JSON.stringify({ error: "validate_failed", status: validate.status, detail: validate.body }));
    return;
  }

  const list = await request("GET", "/api/providers?provider=nvidia", null, cookie);
  const listData = parseJson(list.body);
  const connections = Array.isArray(listData)
    ? listData
    : listData.connections || listData.data || [];
  const hasPkf = connections.some(
    (item) => item && (item.name === "pkf-nvidia" || String(item.name || "").includes("pkf"))
  );

  if (!hasPkf) {
    const created = await request(
      "POST",
      "/api/providers",
      { provider: "nvidia", apiKey: nvidiaKey, name: "pkf-nvidia" },
      cookie
    );
    const createdData = parseJson(created.body);
    if (created.status >= 400 && !createdData.id && !createdData.success) {
      console.log(JSON.stringify({ error: "create_failed", status: created.status, detail: created.body }));
      return;
    }
  }

  console.log(
    JSON.stringify({
      ok: true,
      validate: validate.status,
      connections: connections.length + (hasPkf ? 0 : 1),
      hint_model: "nvidia/meta/llama-3.3-70b-instruct",
    })
  );
})().catch((err) => console.log(JSON.stringify({ error: String(err) })));
NODE

echo "==> NVIDIA configurada. Use modelos nvidia/... no combo 9Router."
