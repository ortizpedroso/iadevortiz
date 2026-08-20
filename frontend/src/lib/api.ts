function normalizeToken(raw: string): string {
  const value = raw.trim();
  if (value.toLowerCase().startsWith("bearer ")) {
    return value.slice(7).trim();
  }
  return value;
}

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

export function wsProtocols(): string[] | undefined {
  const token = getToken();
  return token ? [`pkf-token.${token}`] : undefined;
}

export function wsUrl(): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const token = getToken();
  const qs = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${proto}://${location.host}/ws${qs}`;
}

export function previewUrl(path: string): string {
  const token = getToken();
  const qs = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${location.origin}${path}${qs}`;
}
