export function getToken(): string {
  const fromUrl = new URLSearchParams(location.search).get("token");
  if (fromUrl) {
    sessionStorage.setItem("pkf_token", fromUrl);
    return fromUrl;
  }
  return sessionStorage.getItem("pkf_token") || "";
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

export function previewUrl(path: string): string {
  const token = getToken();
  const qs = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${location.origin}${path}${qs}`;
}
