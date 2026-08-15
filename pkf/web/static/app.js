const $ = (sel) => document.querySelector(sel);
const messagesEl = $("#messages");
const emptyEl = $("#empty-state");
const promptEl = $("#prompt");
const sendBtn = $("#send");
const threadEl = $("#thread");

let socket = null;
let busy = false;
let session = {};
let authRequired = false;
let previewPath = null;
let socketReady = false;

function getToken() {
  const fromUrl = new URLSearchParams(location.search).get("token");
  if (fromUrl) {
    sessionStorage.setItem("pkf_token", fromUrl);
    return fromUrl;
  }
  return sessionStorage.getItem("pkf_token") || "";
}

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function wsUrl() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const token = getToken();
  const qs = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${proto}://${location.host}/ws${qs}`;
}

function showAuthGate() {
  const token = prompt("Informe o token de acesso da PKF:");
  if (!token) return;
  sessionStorage.setItem("pkf_token", token);
  location.reload();
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderMarkdown(src) {
  const escaped = escapeHtml(src || "");
  const parts = escaped.split(/```([\s\S]*?)```/g);
  let html = "";
  parts.forEach((part, index) => {
    if (index % 2 === 1) {
      const nl = part.indexOf("\n");
      const lang = nl === -1 ? "" : part.slice(0, nl);
      const code = nl === -1 ? part : part.slice(nl + 1);
      html += `<pre><code data-lang="${lang.trim()}">${code}</code></pre>`;
      return;
    }
    html += part
      .replace(/^### (.+)$/gm, "<h3>$1</h3>")
      .replace(/^## (.+)$/gm, "<h2>$1</h2>")
      .replace(/^# (.+)$/gm, "<h1>$1</h1>")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/^\- (.+)$/gm, "<li>$1</li>")
      .replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>")
      .replace(/\n{2,}/g, "</p><p>")
      .replace(/^(?!<[uhl]|<p|<pre)/, "<p>")
      .replace(/(?!>)$/, "</p>");
  });
  return html;
}

function showMessages() {
  emptyEl.hidden = true;
  messagesEl.hidden = false;
}

function scrollThread() {
  threadEl.scrollTop = threadEl.scrollHeight;
}

function addMessage({ role, content }) {
  showMessages();
  const article = document.createElement("article");
  article.className = `msg ${role}`;
  const who = role === "user" ? "Você" : "PKF";
  article.innerHTML = `
    <div class="msg-meta"><span>${who}</span></div>
    <div class="bubble">${role === "user" ? `<p>${escapeHtml(content)}</p>` : renderMarkdown(content)}</div>
  `;
  messagesEl.appendChild(article);
  scrollThread();
}

function addThinking() {
  removeTransient();
  const el = document.createElement("div");
  el.className = "msg thinking-row";
  el.dataset.transient = "1";
  el.innerHTML = `<div class="thinking"><b></b>PKF está trabalhando…</div>`;
  messagesEl.appendChild(el);
  showMessages();
  scrollThread();
}

function addError(content) {
  removeTransient();
  addMessage({ role: "error", content });
  const last = messagesEl.lastElementChild;
  if (last) last.classList.add("error");
}

function removeTransient(sel = "[data-transient]") {
  messagesEl.querySelectorAll(sel).forEach((node) => node.remove());
}

function setBusy(next) {
  busy = next;
  sendBtn.disabled = busy || !promptEl.value.trim();
  $("#conn-dot").dataset.state = next ? "busy" : socketReady ? "on" : "off";
  $("#header-status").textContent = next ? "Trabalhando…" : socketReady ? "Pronto" : "Conectando…";
}

function previewUrl(path) {
  const token = getToken();
  const qs = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${location.origin}${path}${qs}`;
}

function updatePreviewControls(preview) {
  const actions = $("#preview-actions");
  const external = $("#preview-external");
  if (preview?.available && preview.path) {
    previewPath = preview.path;
    actions.hidden = false;
    external.href = previewUrl(preview.path);
  } else {
    previewPath = null;
    actions.hidden = true;
  }
}

function openPreviewSide() {
  if (!previewPath) return;
  const pane = $("#preview-pane");
  const frame = $("#preview-frame");
  pane.hidden = false;
  $("#content-split").classList.add("with-preview");
  frame.src = previewUrl(previewPath);
}

function closePreviewSide() {
  $("#preview-pane").hidden = true;
  $("#content-split").classList.remove("with-preview");
  $("#preview-frame").src = "about:blank";
}

function showProgress(message) {
  const el = $("#progress-banner");
  if (!message) {
    el.hidden = true;
    el.textContent = "";
    return;
  }
  el.hidden = false;
  el.textContent = message;
}

function applySession(data) {
  session = { ...session, ...data };
  const project = data.project_name || data.project;
  $("#meta-project").textContent = project && project !== "(sem projeto ativo)" ? project : "Nenhum ainda";
  updatePreviewControls(data.project_preview || data.preview);
  const banner = $("#provider-banner");
  if (data.provider_ok === false && data.provider_error) {
    banner.hidden = false;
    banner.textContent = data.provider_error;
  } else if (data.provider_ok) {
    banner.hidden = true;
    banner.textContent = "";
  }
}

function handleEvent(event) {
  if (event.type === "progress") {
    showProgress(event.message);
    addThinking();
    return;
  }
  if (event.type === "session") {
    applySession(event);
    return;
  }
  if (event.type === "error") {
    setBusy(false);
    showProgress("");
    addError(event.content);
    return;
  }
  if (event.type === "done") {
    removeTransient();
    addMessage(event);
    applySession(event);
    setBusy(false);
    showProgress("");
    if (event.project_preview?.available) {
      updatePreviewControls(event.project_preview);
    }
  }
}

function connect() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }
  socketReady = false;
  setBusy(false);
  socket = new WebSocket(wsUrl());
  socket.addEventListener("open", () => {
    socketReady = true;
    $("#conn-dot").dataset.state = busy ? "busy" : "on";
    $("#header-status").textContent = busy ? "Trabalhando…" : "Pronto";
    autoGrow();
  });
  socket.addEventListener("message", (ev) => {
    handleEvent(JSON.parse(ev.data));
  });
  socket.addEventListener("close", (ev) => {
    socketReady = false;
    $("#conn-dot").dataset.state = "off";
    $("#header-status").textContent = "Reconectando…";
    if (authRequired && ev.code === 4401) {
      showAuthGate();
      return;
    }
    setTimeout(connect, 1500);
  });
  socket.addEventListener("error", () => {
    socketReady = false;
  });
}

async function bootstrap() {
  try {
    const health = await fetch("/api/health");
    if (health.ok) {
      const info = await health.json();
      authRequired = !!info.auth_required;
    }
    if (authRequired && !getToken()) {
      showAuthGate();
      return;
    }
    const res = await fetch("/api/session", { headers: authHeaders() });
    if (res.status === 401) {
      authRequired = true;
      showAuthGate();
      return;
    }
    const data = await res.json();
    applySession(data.session || {});
    (data.messages || []).forEach((msg) => addMessage(msg));
  } catch {
    addError("Não foi possível carregar a sessão. Você ainda pode enviar mensagens.");
  }
}

function sendMessage(text) {
  const content = text.trim();
  if (!content || busy) return;
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    addError("Ainda conectando ao servidor… aguarde um instante e tente de novo.");
    connect();
    return;
  }
  addMessage({ role: "user", content });
  addThinking();
  setBusy(true);
  socket.send(JSON.stringify({ type: "message", content }));
  promptEl.value = "";
  autoGrow();
  sendBtn.disabled = true;
}

function autoGrow() {
  promptEl.style.height = "auto";
  promptEl.style.height = `${Math.min(promptEl.scrollHeight, 180)}px`;
  sendBtn.disabled = busy || !promptEl.value.trim();
}

$("#composer").addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(promptEl.value);
});

promptEl.addEventListener("input", autoGrow);
promptEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage(promptEl.value);
  }
});

document.querySelectorAll("[data-fill]").forEach((btn) => {
  btn.addEventListener("click", () => sendMessage(btn.dataset.fill));
});

$("#new-chat").addEventListener("click", async () => {
  if (!confirm("Começar um novo projeto? O histórico desta conversa será limpo.")) return;
  await fetch("/api/reset", { method: "POST", headers: authHeaders() });
  messagesEl.innerHTML = "";
  messagesEl.hidden = true;
  emptyEl.hidden = false;
  closePreviewSide();
  applySession({ project: null, project_name: null, project_preview: { available: false } });
});

$("#toggle-sidebar").addEventListener("click", () => {
  $("#sidebar").classList.toggle("open");
});

$("#preview-side").addEventListener("click", openPreviewSide);
$("#close-preview").addEventListener("click", closePreviewSide);

connect();
bootstrap();
