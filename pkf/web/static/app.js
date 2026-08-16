const $ = (sel) => document.querySelector(sel);

const messagesEl = $("#messages");
const emptyEl = $("#empty-state");
const promptEl = $("#prompt");
const sendBtn = $("#send");
const threadEl = $("#thread");
const loadingSkeleton = $("#loading-skeleton");
const statusLive = $("#status-live");
const modalRoot = $("#modal-root");
const sidebarEl = $("#sidebar");
const sidebarBackdrop = $("#sidebar-backdrop");
const toggleSidebarBtn = $("#toggle-sidebar");

let socket = null;
let busy = false;
let session = {};
let authRequired = false;
let previewPath = null;
let socketReady = false;
let confirmResolver = null;
let lastFocusedBeforeModal = null;

const TASK_ICONS = {
  done: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M20 6L9 17l-5-5"/></svg>`,
  running: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>`,
  failed: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M18 6L6 18M6 6l12 12"/></svg>`,
  pending: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg>`,
};

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

function announceStatus(text) {
  if (statusLive) statusLive.textContent = text;
}

function openModal(modalEl) {
  lastFocusedBeforeModal = document.activeElement;
  modalRoot.hidden = false;
  modalEl.hidden = false;
  document.body.style.overflow = "hidden";
  const focusable = modalEl.querySelector("input, button:not([hidden])");
  if (focusable) focusable.focus();
}

function closeModals() {
  modalRoot.hidden = true;
  $("#auth-modal").hidden = true;
  $("#confirm-modal").hidden = true;
  document.body.style.overflow = "";
  if (confirmResolver) {
    confirmResolver(false);
    confirmResolver = null;
  }
  if (lastFocusedBeforeModal?.focus) lastFocusedBeforeModal.focus();
}

function showAuthGate() {
  const input = $("#auth-token-input");
  input.value = "";
  openModal($("#auth-modal"));
}

function showConfirm(message, title = "Confirmar ação") {
  return new Promise((resolve) => {
    confirmResolver = resolve;
    $("#confirm-modal-title").textContent = title;
    $("#confirm-modal-message").textContent = message;
    openModal($("#confirm-modal"));
  });
}

function setSidebarOpen(open) {
  sidebarEl.classList.toggle("open", open);
  sidebarBackdrop.hidden = !open;
  sidebarBackdrop.setAttribute("aria-hidden", open ? "false" : "true");
  if (toggleSidebarBtn) toggleSidebarBtn.setAttribute("aria-expanded", open ? "true" : "false");
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
      html += `<div class="code-block"><button type="button" class="copy-code-btn" aria-label="Copiar código">Copiar</button><pre><code data-lang="${lang.trim()}">${code}</code></pre></div>`;
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
      .replace(/^(?!<[uhl]|<p|<pre|<div)/, "<p>")
      .replace(/(?!>)$/, "</p>");
  });
  return html;
}

function attachCopyButtons(root) {
  root.querySelectorAll(".copy-code-btn").forEach((btn) => {
    if (btn.dataset.bound) return;
    btn.dataset.bound = "1";
    btn.addEventListener("click", async () => {
      const code = btn.parentElement?.querySelector("code");
      if (!code) return;
      try {
        await navigator.clipboard.writeText(code.textContent || "");
        btn.textContent = "Copiado!";
        btn.classList.add("copied");
        setTimeout(() => {
          btn.textContent = "Copiar";
          btn.classList.remove("copied");
        }, 2000);
      } catch {
        btn.textContent = "Erro";
      }
    });
  });
}

function showLoading(show) {
  loadingSkeleton.hidden = !show;
  loadingSkeleton.setAttribute("aria-busy", show ? "true" : "false");
  if (show) {
    emptyEl.hidden = true;
    messagesEl.hidden = true;
  }
}

function showMessages() {
  loadingSkeleton.hidden = true;
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
  const who = role === "user" ? "Você" : role === "error" ? "Erro" : "PKF";
  article.innerHTML = `
    <div class="msg-meta"><span>${who}</span></div>
    <div class="bubble">${role === "user" ? `<p>${escapeHtml(content)}</p>` : renderMarkdown(content)}</div>
  `;
  messagesEl.appendChild(article);
  attachCopyButtons(article);
  scrollThread();
}

function addThinking() {
  removeTransient();
  const el = document.createElement("div");
  el.className = "msg thinking-row";
  el.dataset.transient = "1";
  el.innerHTML = `<div class="thinking"><b aria-hidden="true"></b>PKF está trabalhando…</div>`;
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
  const connState = next ? "busy" : socketReady ? "on" : "off";
  $("#conn-dot").dataset.state = connState;
  const label = next ? "Trabalhando…" : socketReady ? "Pronto" : "Conectando…";
  $("#header-status").textContent = label;
  announceStatus(label);
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
  setSidebarOpen(false);
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

function taskStatusIcon(status) {
  const key = TASK_ICONS[status] ? status : "pending";
  const label = { done: "Concluída", running: "Em andamento", failed: "Falhou", pending: "Pendente" }[key];
  return `<span class="task-icon" aria-label="${label}">${TASK_ICONS[key]}</span>`;
}

function renderTaskNode(node) {
  const status = node.status || "pending";
  let html = `<li class="${status}">${taskStatusIcon(status)}<span>${escapeHtml(node.title || node.id)}</span>`;
  if (node.children?.length) {
    html += "<ul>" + node.children.map(renderTaskNode).join("") + "</ul>";
  }
  html += "</li>";
  return html;
}

function renderTaskTree(tasks) {
  const el = $("#task-tree");
  if (!el) return;
  if (!tasks?.length) {
    el.innerHTML = "<li><span>Nenhuma tarefa</span></li>";
    return;
  }
  el.innerHTML = tasks.map(renderTaskNode).join("");
}

async function loadTasks() {
  try {
    const res = await fetch("/api/tasks", { headers: authHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    renderTaskTree(data.tasks);
  } catch {
    /* ignore */
  }
}

async function loadChanges() {
  try {
    const res = await fetch("/api/changes", { headers: authHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    const el = $("#changes-list");
    if (!el) return;
    const items = data.changes || [];
    el.innerHTML =
      items
        .slice()
        .reverse()
        .map((c) => `<li>${escapeHtml(c.path)} <small>(${escapeHtml(c.action)})</small></li>`)
        .join("") || "<li>(nenhuma ainda)</li>";
  } catch {
    /* ignore */
  }
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
  if (event.type === "progress" || event.type === "task_progress") {
    showProgress(event.message);
    addThinking();
    return;
  }
  if (event.type === "task_tree") {
    renderTaskTree(event.tasks);
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
    loadChanges();
    loadTasks();
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
    setBusy(busy);
  });
  socket.addEventListener("message", (ev) => {
    handleEvent(JSON.parse(ev.data));
  });
  socket.addEventListener("close", (ev) => {
    socketReady = false;
    $("#conn-dot").dataset.state = "off";
    $("#header-status").textContent = "Reconectando…";
    announceStatus("Reconectando…");
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
  showLoading(true);
  try {
    const health = await fetch("/api/health");
    if (health.ok) {
      const info = await health.json();
      authRequired = !!info.auth_required;
    }
    if (authRequired && !getToken()) {
      showLoading(false);
      emptyEl.hidden = false;
      showAuthGate();
      return;
    }
    const res = await fetch("/api/session", { headers: authHeaders() });
    if (res.status === 401) {
      authRequired = true;
      showLoading(false);
      emptyEl.hidden = false;
      showAuthGate();
      return;
    }
    const data = await res.json();
    applySession(data.session || {});
    renderTaskTree((data.session || {}).tasks);
    if ((data.messages || []).length) {
      data.messages.forEach((msg) => addMessage(msg));
    } else {
      showLoading(false);
      emptyEl.hidden = false;
      messagesEl.hidden = true;
    }
    loadChanges();
    loadTasks();
  } catch {
    showLoading(false);
    emptyEl.hidden = false;
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
  const ok = await showConfirm(
    "Começar um novo projeto? O histórico desta conversa será limpo.",
    "Novo projeto"
  );
  if (!ok) return;
  await fetch("/api/reset", { method: "POST", headers: authHeaders() });
  messagesEl.innerHTML = "";
  messagesEl.hidden = true;
  emptyEl.hidden = false;
  closePreviewSide();
  applySession({ project: null, project_name: null, project_preview: { available: false } });
  renderTaskTree([]);
  loadChanges();
});

toggleSidebarBtn?.addEventListener("click", () => {
  setSidebarOpen(!sidebarEl.classList.contains("open"));
});

sidebarBackdrop?.addEventListener("click", () => setSidebarOpen(false));

$("#preview-side").addEventListener("click", openPreviewSide);
$("#close-preview").addEventListener("click", closePreviewSide);

$("#auth-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const token = $("#auth-token-input").value.trim();
  if (!token) return;
  sessionStorage.setItem("pkf_token", token);
  closeModals();
  location.reload();
});

$("#confirm-ok").addEventListener("click", () => {
  if (confirmResolver) {
    confirmResolver(true);
    confirmResolver = null;
  }
  closeModals();
});

modalRoot.querySelectorAll("[data-modal-close]").forEach((el) => {
  el.addEventListener("click", closeModals);
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    if (!modalRoot.hidden) {
      closeModals();
      return;
    }
    if (sidebarEl.classList.contains("open")) {
      setSidebarOpen(false);
    }
  }
});

connect();
bootstrap();
