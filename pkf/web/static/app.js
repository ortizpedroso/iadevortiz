const $ = (sel) => document.querySelector(sel);
const messagesEl = $("#messages");
const emptyEl = $("#empty-state");
const promptEl = $("#prompt");
const sendBtn = $("#send");
const threadEl = $("#thread");

const AGENT_LABELS = {
  architect: "Architect",
  frontend: "Frontend",
  backend: "Backend",
  logic: "Logic",
  reviewer: "Reviewer",
  tester: "Tester",
  generalista: "Generalista",
  sistema: "Sistema",
};

let socket = null;
let busy = false;
let session = {};
let authRequired = false;

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

function addMessage({ role, content, agent }) {
  showMessages();
  const article = document.createElement("article");
  article.className = `msg ${role}`;
  const who = role === "user" ? "Você" : AGENT_LABELS[agent] || agent || "PKF";
  article.innerHTML = `
    <div class="msg-meta">
      <span>${who}</span>
      ${agent && role !== "user" ? `<span class="badge">${agent}</span>` : ""}
    </div>
    <div class="bubble">${role === "user" ? `<p>${escapeHtml(content)}</p>` : renderMarkdown(content)}</div>
  `;
  messagesEl.appendChild(article);
  scrollThread();
  return article;
}

function addThinking(agent) {
  removeTransient();
  const el = document.createElement("div");
  el.className = "msg thinking-row";
  el.dataset.transient = "1";
  el.innerHTML = `<div class="thinking"><b></b>${AGENT_LABELS[agent] || agent} está trabalhando…</div>`;
  messagesEl.appendChild(el);
  showMessages();
  scrollThread();
}

function addTool({ name, arguments: args, result, status }) {
  removeTransient(".thinking-row");
  const details = document.createElement("details");
  details.className = "tool";
  details.open = status === "running";
  const preview = typeof args === "object" ? JSON.stringify(args) : String(args || "");
  details.innerHTML = `
    <summary>${status === "running" ? "Rodando" : "Ferramenta"} · ${escapeHtml(name)}</summary>
    <pre>${escapeHtml(preview)}${result ? `\n\n${escapeHtml(result)}` : ""}</pre>
  `;
  const wrap = document.createElement("div");
  wrap.className = "msg";
  wrap.appendChild(details);
  messagesEl.appendChild(wrap);
  showMessages();
  scrollThread();
}

function addError(content) {
  removeTransient();
  addMessage({ role: "error", content, agent: "sistema" });
  const last = messagesEl.lastElementChild;
  if (last) last.classList.add("error");
}

function removeTransient(sel = "[data-transient]") {
  messagesEl.querySelectorAll(sel).forEach((node) => node.remove());
}

function setBusy(next) {
  busy = next;
  sendBtn.disabled = busy || !promptEl.value.trim();
  $("#conn-dot").dataset.state = next ? "busy" : socket?.readyState === 1 ? "on" : "off";
}

function renderAgents(active) {
  const list = $("#agent-list");
  const names = session.agents || Object.keys(AGENT_LABELS);
  list.innerHTML = names
    .filter((name) => AGENT_LABELS[name])
    .map(
      (name) =>
        `<li class="${name === active ? "active" : ""}"><i></i>${AGENT_LABELS[name]}</li>`
    )
    .join("");
}

function applySession(data) {
  session = { ...session, ...data };
  $("#meta-phase").textContent = data.phase || "IDLE";
  $("#meta-spec").textContent = data.active_spec || "—";
  $("#meta-agent").textContent = data.last_agent || "—";
  $("#meta-workspace").textContent = data.workspace || "—";
  $("#meta-provider").textContent = data.model ? `${data.provider} · ${data.model}` : data.provider || "—";
  $("#header-agent").textContent = data.last_agent
    ? AGENT_LABELS[data.last_agent] || data.last_agent
    : "Pronto";
  renderAgents(data.last_agent);
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
  if (event.type === "session") {
    applySession(event);
    return;
  }
  if (event.type === "routing") {
    applySession({ last_agent: event.agent });
    if (event.kind !== "command") addThinking(event.agent);
    return;
  }
  if (event.type === "thinking") {
    addThinking(event.agent);
    return;
  }
  if (event.type === "tool") {
    addTool(event);
    return;
  }
  if (event.type === "error") {
    setBusy(false);
    addError(event.content);
    return;
  }
  if (event.type === "done") {
    removeTransient();
    addMessage(event);
    applySession(event);
    setBusy(false);
  }
}

function connect() {
  socket = new WebSocket(wsUrl());
  socket.addEventListener("open", () => {
    $("#conn-dot").dataset.state = "on";
  });
  socket.addEventListener("message", (ev) => {
    handleEvent(JSON.parse(ev.data));
  });
  socket.addEventListener("close", (ev) => {
    $("#conn-dot").dataset.state = "off";
    if (authRequired && ev.code === 4401) {
      showAuthGate();
      return;
    }
    setTimeout(connect, 1500);
  });
}

async function bootstrap() {
  const health = await fetch("/api/health");
  if (health.ok) {
    const info = await health.json();
    authRequired = !!info.auth_required;
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
}

function sendMessage(text) {
  const content = text.trim();
  if (!content || busy || !socket || socket.readyState !== 1) return;
  addMessage({ role: "user", content });
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

document.querySelectorAll("[data-insert]").forEach((btn) => {
  btn.addEventListener("click", () => {
    promptEl.value = btn.dataset.insert;
    promptEl.focus();
    autoGrow();
  });
});

document.querySelectorAll("[data-fill]").forEach((btn) => {
  btn.addEventListener("click", () => sendMessage(btn.dataset.fill));
});

$("#new-chat").addEventListener("click", async () => {
  if (!confirm("Começar um novo chat? O histórico desta tela será limpo.")) return;
  await fetch("/api/reset", { method: "POST", headers: authHeaders() });
  messagesEl.innerHTML = "";
  messagesEl.hidden = true;
  emptyEl.hidden = false;
  applySession({ phase: "IDLE", active_spec: null, last_agent: null });
});

$("#toggle-sidebar").addEventListener("click", () => {
  $("#sidebar").classList.toggle("open");
});

bootstrap().then(connect).catch(() => connect());
