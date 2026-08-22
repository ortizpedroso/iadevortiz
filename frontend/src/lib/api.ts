function normalizeToken(raw: string): string {
  const value = raw.trim();
  if (value.toLowerCase().startsWith("bearer ")) {
    return value.slice(7).trim();
  }
  return value;
}

let cachedPreviewToken = "";
let cachedPreviewTokenPath = "";
let cachedPreviewTokenExpiresAt = 0;

export function getToken(): string {
  const fromUrl = new URLSearchParams(location.search).get("token");
  if (fromUrl) {
    const token = normalizeToken(fromUrl);
    sessionStorage.setItem("pkf_token", token);
    return token;
  }
  return normalizeToken(sessionStorage.getItem("pkf_token") || "");
}

export function authHeaders(): HeadersInit {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function wsUrl(): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const token = getToken();
  const qs = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${proto}://${location.host}/ws${qs}`;
}

export function wsProtocols(): string[] | undefined {
  const token = getToken();
  return token ? [`pkf-token.${token}`] : undefined;
}

export function setPreviewToken(token: string, path: string, expiresInSec = 900): void {
  cachedPreviewToken = token;
  cachedPreviewTokenPath = path;
  cachedPreviewTokenExpiresAt = Date.now() + expiresInSec * 1000;
}

async function fetchPreviewToken(path: string): Promise<string> {
  const res = await fetch("/api/preview-token", { headers: authHeaders() });
  if (!res.ok) return "";
  const data = await res.json();
  if (data.token) {
    setPreviewToken(data.token, path, data.expires_in || 900);
    return data.token as string;
  }
  return "";
}

export async function previewUrl(path: string): Promise<string> {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  let token = cachedPreviewToken;
  if (
    !token ||
    cachedPreviewTokenPath !== normalized ||
    Date.now() >= cachedPreviewTokenExpiresAt - 30_000
  ) {
    token = await fetchPreviewToken(normalized);
  }
  const qs = token ? `?preview_token=${encodeURIComponent(token)}` : "";
  return `${location.origin}${normalized}${qs}`;
}
