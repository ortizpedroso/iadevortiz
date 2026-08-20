import { useCallback, useEffect, useRef, useState } from "react";
import { AuthModal } from "./components/AuthModal";
import { Composer } from "./components/Composer";
import { MessageList } from "./components/MessageList";
import { Sidebar } from "./components/Sidebar";
import { SpecPanel } from "./components/SpecPanel";
import { authHeaders, getToken, previewUrl, wsUrl } from "./lib/api";
import type { ChatItem, Message, ProjectItem, SessionSnapshot, SpecPreview, TaskNode, WsEvent } from "./types";

const EMPTY_SESSION: SessionSnapshot = {};

export default function App() {
  const [authRequired, setAuthRequired] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const [panel, setPanel] = useState<"project" | "spec" | null>("project");
  const [sessionReady, setSessionReady] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [session, setSession] = useState<SessionSnapshot>(EMPTY_SESSION);
  const [specPreview, setSpecPreview] = useState<SpecPreview | null>(null);
  const [tasks, setTasks] = useState<TaskNode[]>([]);
  const [changes, setChanges] = useState<{ path: string; action: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [progress, setProgress] = useState("");
  const [status, setStatus] = useState("Conectando…");
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewSrc, setPreviewSrc] = useState("");
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [activeProvider, setActiveProvider] = useState<string | null>(null);
  const [chats, setChats] = useState<ChatItem[]>([]);
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const socketRef = useRef<WebSocket | null>(null);
  const sessionBootstrappedRef = useRef(false);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<number | null>(null);
  const intentionalCloseRef = useRef(false);
  const activeSocketIdRef = useRef(0);
  const authRequiredRef = useRef(false);
  const wsConnectedRef = useRef(false);
  const useHttpFallbackRef = useRef(false);
  const [useHttpFallback, setUseHttpFallback] = useState(false);
  const applySessionRef = useRef<(data: SessionSnapshot, replace?: boolean) => void>(() => {});
  const loadChangesRef = useRef<() => Promise<void>>(async () => {});

  const applyLibrary = useCallback((library?: { chats?: ChatItem[]; projects?: ProjectItem[] }) => {
    if (!library) return;
    if (library.chats) setChats(library.chats);
    if (library.projects) setProjects(library.projects);
  }, []);

  const loadLibrary = useCallback(async () => {
    try {
      const res = await fetch("/api/library", { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setChats(data.chats || []);
        setProjects(data.projects || []);
      }
    } catch {
      /* ignore */
    }
  }, []);

  const loadChanges = useCallback(async () => {
    try {
      const res = await fetch("/api/changes", { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setChanges(data.changes || []);
      }
    } catch {
      /* ignore */
    }
  }, []);

  const applySession = useCallback((data: SessionSnapshot, replace = false) => {
    setSession(replace ? data : (current) => ({ ...current, ...data }));
    if ("tasks" in data) setTasks(data.tasks || []);
    if (data.spec_preview) {
      setSpecPreview(data.spec_preview);
      if (data.spec_preview.status === "pending_approval") setPanel("spec");
    } else if (replace) {
      setSpecPreview(null);
      if (panel === "spec") setPanel("project");
    }
    if (data.project_preview?.available && data.project_preview.path) {
      setPreviewSrc(previewUrl(data.project_preview.path));
    } else if (replace) {
      setPreviewSrc("");
      setPreviewOpen(false);
    }
    if (data.active_agent) setActiveAgent(data.active_agent);
  }, [panel]);

  applySessionRef.current = applySession;
  loadChangesRef.current = loadChanges;

  const invalidateSocket = useCallback(() => {
    activeSocketIdRef.current += 1;
  }, []);

  const connect = useCallback((force = false) => {
    if (!force && useHttpFallbackRef.current) return;
    if (authRequiredRef.current && !getToken()) {
      setAuthOpen(true);
      setStatus("Token necessário");
      return;
    }
    if (socketRef.current?.readyState === WebSocket.OPEN) return;
    if (socketRef.current?.readyState === WebSocket.CONNECTING) return;
    if (reconnectTimerRef.current) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    const token = getToken();
    if (token && !new URLSearchParams(window.location.search).get("token")) {
      const url = new URL(window.location.href);
      url.searchParams.set("token", token);
      window.history.replaceState({}, "", url.toString());
    }
    const socketId = activeSocketIdRef.current;
    const ws = new WebSocket(wsUrl());
    socketRef.current = ws;
    ws.onopen = () => {
      if (socketId !== activeSocketIdRef.current || ws !== socketRef.current) return;
      wsConnectedRef.current = true;
      useHttpFallbackRef.current = false;
      setUseHttpFallback(false);
      reconnectAttemptsRef.current = 0;
      setStatus("Pronto");
    };
    ws.onclose = (ev) => {
      if (socketId !== activeSocketIdRef.current) return;
      if (ws !== socketRef.current) return;
      wsConnectedRef.current = false;
      socketRef.current = null;
      if (intentionalCloseRef.current || ev.code === 1000) return;
      const likelyAuthFailure =
        ev.code === 1008 ||
        (authRequiredRef.current && !getToken());
      if (likelyAuthFailure) {
        if (ev.code === 1008) {
          sessionStorage.removeItem("pkf_token");
        }
        setAuthOpen(true);
        setStatus(ev.code === 1008 ? "Token inválido" : "Token necessário");
        return;
      }
      if (ev.code === 1011) {
        setStatus("Erro de sessão");
        return;
      }
      reconnectAttemptsRef.current += 1;
      if (reconnectAttemptsRef.current >= 8) {
        useHttpFallbackRef.current = true;
        setUseHttpFallback(true);
        setStatus("Modo HTTP (sem tempo real)");
        return;
      }
      setStatus(`Reconectando… (${ev.code})`);
      reconnectTimerRef.current = window.setTimeout(() => connect(false), Math.min(2000 * reconnectAttemptsRef.current, 10000));
    };
    ws.onerror = () => {
      if (ws.readyState !== WebSocket.OPEN) {
        setStatus("Erro de conexão…");
      }
    };
    ws.onmessage = (ev) => {
      const event: WsEvent = JSON.parse(ev.data);
      if (event.type === "session") {
        sessionBootstrappedRef.current = true;
        applySessionRef.current(event as SessionSnapshot, true);
        return;
      }
      if (event.type === "spec_preview" && event.spec) {
        setSpecPreview(event.spec);
        setPanel("spec");
        return;
      }
      if (event.type === "progress" || event.type === "task_progress") {
        setProgress(event.message || "");
        setThinking(true);
        return;
      }
      if (event.type === "active_agent") {
        if (event.agent) setActiveAgent(String(event.agent));
        if (event.provider) setActiveProvider(String(event.provider));
        return;
      }
      if (event.type === "task_tree" && event.tasks) {
        setTasks(event.tasks);
        return;
      }
      if (event.type === "error") {
        setBusy(false);
        setThinking(false);
        setProgress("");
        const content = event.content || "Erro";
        setMessages((m) => [...m, { role: "error", content }]);
        if (content.toLowerCase().includes("token")) {
          sessionStorage.removeItem("pkf_token");
          setAuthOpen(true);
          setStatus("Token inválido");
          intentionalCloseRef.current = true;
          ws.close(1000, "auth");
        }
        return;
      }
      if (event.type === "done") {
        setThinking(false);
        setBusy(false);
        setProgress("");
        setActiveAgent(null);
        setActiveProvider(null);
        setMessages((m) => [
          ...m,
          { role: "assistant", content: event.content || "", agent: event.agent as string },
        ]);
        applySessionRef.current(event as SessionSnapshot);
        loadChangesRef.current();
      }
    };
  }, []);

  useEffect(() => {
    let active = true;

    async function boot() {
      let serverOk = false;
      try {
        const healthRes = await fetch("/api/health");
        if (healthRes.ok) {
          serverOk = true;
          const info = await healthRes.json();
          setAuthRequired(!!info.auth_required);
          authRequiredRef.current = !!info.auth_required;
          if (info.auth_required && !getToken()) {
            setAuthOpen(true);
            setStatus("Token necessário");
            return;
          }
        }
      } catch {
        setStatus("Servidor indisponível");
        return;
      }
      if (!serverOk) {
        setStatus("Servidor indisponível");
        return;
      }
      let sessionOk = false;
      try {
        const res = await fetch("/api/session", { headers: authHeaders() });
        if (res.status === 401) {
          sessionStorage.removeItem("pkf_token");
          setAuthOpen(true);
          setStatus("Token necessário");
          return;
        }
        if (res.ok) {
          sessionOk = true;
          const data = await res.json();
          applySession(data.session, true);
          setMessages(data.messages || []);
          applyLibrary(data.library);
          sessionBootstrappedRef.current = true;
          const token = getToken();
          if (token && !new URLSearchParams(window.location.search).get("token")) {
            const url = new URL(window.location.href);
            url.searchParams.set("token", token);
            window.history.replaceState({}, "", url.toString());
          }
        }
      } catch {
        if (authRequiredRef.current) {
          setStatus("Servidor indisponível");
          return;
        }
      }
      if (!sessionOk && authRequiredRef.current) {
        setAuthOpen(true);
        setStatus("Token necessário");
        return;
      }
      if (!sessionBootstrappedRef.current) {
        await loadLibrary();
      } else {
        await loadLibrary();
      }
      await loadChanges();
      if (!active) return;
      setSessionReady(true);
    }
    boot();
    return () => {
      active = false;
    };
  }, [applyLibrary, loadChanges, loadLibrary]);

  useEffect(() => {
    if (!sessionReady) return;
    if (authRequiredRef.current && !getToken()) return;

    intentionalCloseRef.current = false;
    reconnectAttemptsRef.current = 0;
    useHttpFallbackRef.current = false;
    setUseHttpFallback(false);
    const timer = window.setTimeout(() => connect(false), 100);

    return () => {
      window.clearTimeout(timer);
      invalidateSocket();
      intentionalCloseRef.current = true;
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      const ws = socketRef.current;
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        ws.close(1000, "reconnect");
      }
      socketRef.current = null;
      wsConnectedRef.current = false;
    };
  }, [sessionReady, connect, invalidateSocket]);

  useEffect(() => {
    if (!useHttpFallback) return;
    const timer = window.setInterval(() => {
      if (wsConnectedRef.current) return;
      useHttpFallbackRef.current = false;
      reconnectAttemptsRef.current = 0;
      connect(true);
    }, 30000);
    return () => window.clearInterval(timer);
  }, [useHttpFallback, connect]);

  function retryWebSocket() {
    useHttpFallbackRef.current = false;
    setUseHttpFallback(false);
    reconnectAttemptsRef.current = 0;
    invalidateSocket();
    intentionalCloseRef.current = true;
    if (reconnectTimerRef.current) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    const ws = socketRef.current;
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      ws.close(1000, "retry");
    }
    socketRef.current = null;
    wsConnectedRef.current = false;
    intentionalCloseRef.current = false;
    connect(true);
  }

  async function sendMessageHttp(text: string) {
    setMessages((m) => [...m, { role: "user", content: text }]);
    setThinking(true);
    setBusy(true);
    try {
      const res = await fetch("/api/message", {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ content: text }),
      });
      const event = await res.json();
      if (event.type === "error") {
        setMessages((m) => [...m, { role: "error", content: event.content || "Erro" }]);
      } else if (event.type === "done") {
        setMessages((m) => [
          ...m,
          { role: "assistant", content: event.content || "", agent: event.agent as string },
        ]);
        applySessionRef.current(event as SessionSnapshot);
        loadChangesRef.current();
      }
    } catch {
      setMessages((m) => [...m, { role: "error", content: "Falha ao enviar mensagem via HTTP." }]);
    } finally {
      setThinking(false);
      setBusy(false);
      setProgress("");
      setActiveAgent(null);
      setActiveProvider(null);
    }
  }

  function handleAuth(token: string) {
    sessionStorage.setItem("pkf_token", token);
    const url = new URL(window.location.href);
    url.searchParams.set("token", token);
    window.location.replace(url.toString());
  }

  function sendMessage(text: string) {
    if (useHttpFallbackRef.current || useHttpFallback) {
      void sendMessageHttp(text);
      return;
    }
    const ws = socketRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      if (authRequiredRef.current && !getToken()) {
        setAuthOpen(true);
        setMessages((m) => [...m, { role: "error", content: "Informe o token de acesso para continuar." }]);
        return;
      }
      if (sessionReady) {
        void sendMessageHttp(text);
        return;
      }
      setMessages((m) => [...m, { role: "error", content: "Ainda conectando… tente de novo em instantes." }]);
      reconnectAttemptsRef.current = 0;
      connect(false);
      return;
    }
    setMessages((m) => [...m, { role: "user", content: text }]);
    setThinking(true);
    setBusy(true);
    ws.send(JSON.stringify({ type: "message", content: text }));
  }

  async function newProject() {
    if (!confirm("Começar um novo projeto? O histórico desta conversa será limpo.")) return;
    await fetch("/api/reset", { method: "POST", headers: authHeaders() });
    setMessages([]);
    setPreviewOpen(false);
    setSpecPreview(null);
    setSession(EMPTY_SESSION);
    setTasks([]);
    loadChanges();
    loadLibrary();
  }

  async function newChat() {
    const res = await fetch("/api/chats", { method: "POST", headers: authHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    setMessages([]);
    setSpecPreview(null);
    applyLibrary(data.library);
    if (data.session) applySession(data.session, true);
  }

  async function selectChat(id: string) {
    const res = await fetch(`/api/chats/${id}/activate`, { method: "POST", headers: authHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    setMessages(data.messages || []);
    applySession(data.session || {}, true);
    loadLibrary();
    loadChanges();
  }

  async function deleteChat(id: string) {
    if (!confirm("Excluir este chat?")) return;
    const res = await fetch(`/api/chats/${id}`, { method: "DELETE", headers: authHeaders() });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setMessages((m) => [
        ...m,
        { role: "error", content: data?.error || "Não foi possível excluir o chat." },
      ]);
      return;
    }
    applyLibrary(data.library);
    setMessages(data.messages || []);
    if (data.session) applySession(data.session, true);
    await loadLibrary();
    loadChanges();
  }

  async function attachChat(chatId: string, projectSlug: string | null) {
    const res = await fetch(`/api/chats/${chatId}/attach`, {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ project_slug: projectSlug }),
    });
    if (!res.ok) return;
    const data = await res.json();
    applyLibrary(data.library);
  }

  async function selectProject(slug: string) {
    const res = await fetch(`/api/projects/${slug}/activate`, { method: "POST", headers: authHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    applySession(data.session || {}, true);
    applyLibrary(data.library);
    loadChanges();
  }

  async function deleteProject(slug: string) {
    const res = await fetch(`/api/projects/${slug}`, { method: "DELETE", headers: authHeaders() });
    if (!res.ok) {
      let message = "Não foi possível excluir o projeto.";
      try {
        const body = await res.json();
        if (body?.error) message = String(body.error);
      } catch {
        /* ignore */
      }
      setMessages((m) => [...m, { role: "error", content: message }]);
      return;
    }
    await loadLibrary();
    const sessionRes = await fetch("/api/session", { headers: authHeaders() });
    if (sessionRes.ok) {
      const payload = await sessionRes.json();
      applySession(payload.session, true);
      loadChanges();
    }
  }

  async function bulkDeleteProjects(slugs: string[], deleteAll = false) {
    const res = await fetch("/api/projects/bulk-delete", {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(deleteAll ? { all: true } : { slugs }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setMessages((m) => [
        ...m,
        { role: "error", content: data?.error || "Não foi possível excluir os projetos." },
      ]);
      return;
    }
    applyLibrary(data.library);
    if (data.session) applySession(data.session, true);
    await loadLibrary();
    loadChanges();
    const failed = data.failed ? Object.keys(data.failed) : [];
    if (failed.length) {
      setMessages((m) => [
        ...m,
        {
          role: "error",
          content: `Alguns projetos não foram excluídos: ${failed.join(", ")}`,
        },
      ]);
    }
  }

  async function renameProject(slug: string, name: string) {
    const res = await fetch(`/api/projects/${slug}`, {
      method: "PATCH",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!res.ok) return;
    const data = await res.json();
    applyLibrary(data.library);
    if (data.session) applySession(data.session, true);
  }

  async function pinProject(slug: string, pinned: boolean) {
    const res = await fetch(`/api/projects/${slug}/pin`, {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ pinned }),
    });
    if (!res.ok) return;
    const data = await res.json();
    applyLibrary(data.library);
  }

  const projectName =
    session.project_name && session.project_name !== "(sem projeto ativo)"
      ? session.project_name
      : "Nenhum ainda";

  const showSpecPanel = panel === "spec" && specPreview && specPreview.status !== "approved";

  return (
    <div className="flex h-full min-h-dvh bg-[var(--pkf-bg-primary)]">
      <AuthModal open={authOpen && authRequired} onSubmit={handleAuth} />

      <a
        href="#main-chat"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:rounded focus:bg-[var(--pkf-accent)] focus:px-3 focus:py-2 focus:text-[var(--pkf-bg-primary)]"
      >
        Ir ao chat
      </a>

      <Sidebar
        open={panel === "project"}
        ready={sessionReady}
        onClose={() => setPanel(null)}
        projectName={projectName}
        tasks={tasks}
        changes={changes}
        onNewProject={newProject}
        database={!!session.database}
        phase={session.phase}
        model={session.model}
        busy={busy}
        chats={chats}
        projects={projects}
        onSelectChat={selectChat}
        onDeleteChat={deleteChat}
        onAttachChat={attachChat}
        onSelectProject={selectProject}
        onDeleteProject={deleteProject}
        onBulkDeleteProjects={bulkDeleteProjects}
        onRenameProject={renameProject}
        onPinProject={pinProject}
        onNewChat={newChat}
      />

      <div className="flex min-w-0 flex-1 flex-col bg-[var(--pkf-bg-primary)]">
        <header className="flex min-h-12 items-center gap-3 border-b border-[var(--pkf-border-soft)] bg-[var(--pkf-bg-primary)] px-4">
          <button
            type="button"
            className="pkf-btn-icon grid h-10 w-10 place-items-center rounded-lg md:hidden"
            aria-label="Abrir menu"
            onClick={() => setPanel(panel === "project" ? null : "project")}
          >
            ☰
          </button>
          <div className="flex min-w-0 flex-col text-sm" aria-live="polite">
            <div className="flex items-center gap-2">
              <span
                className={`h-2 w-2 shrink-0 rounded-full ${
                  busy
                    ? "bg-[var(--pkf-accent)]"
                    : status === "Pronto"
                      ? "bg-emerald-500"
                      : useHttpFallback
                        ? "bg-amber-500"
                        : "bg-[var(--pkf-text-dim)]"
                }`}
              />
              <span className="text-[var(--pkf-muted)]">{busy ? "Trabalhando…" : status}</span>
            </div>
            {(activeAgent || session.provider) && busy ? (
              <span className="truncate text-xs text-[var(--pkf-text-dim)]">
                {activeAgent || session.last_agent || "pkf"}
                {" · "}
                {activeProvider || session.provider || "—"}
                {session.model ? ` · ${session.model}` : ""}
              </span>
            ) : null}
          </div>
          <div className="ml-auto flex gap-2">
            {specPreview && specPreview.status !== "approved" ? (
              <button
                type="button"
                className="hidden min-h-9 rounded-lg border border-[var(--pkf-border)] px-3 text-xs font-medium hover:border-[var(--pkf-accent)]/50 sm:inline-flex sm:items-center"
                onClick={() => setPanel(panel === "spec" ? null : "spec")}
              >
                Spec
              </button>
            ) : null}
            {session.project_preview?.available ? (
              <>
                <button
                  type="button"
                  className="hidden min-h-9 rounded-lg border border-[var(--pkf-border)] px-3 text-xs font-medium hover:border-[var(--pkf-accent)]/50 sm:inline-flex sm:items-center"
                  onClick={() => setPreviewOpen((v) => !v)}
                >
                  {previewOpen ? "Ocultar preview" : "Preview"}
                </button>
                <a
                  href={previewSrc}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex min-h-9 items-center rounded-lg border border-[var(--pkf-border)] px-3 text-xs font-medium hover:border-[var(--pkf-accent)]/50"
                >
                  Abrir ↗
                </a>
              </>
            ) : null}
          </div>
        </header>

        {session.provider_error ? (
          <div className="mx-4 mt-3 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
            {session.provider_error}
          </div>
        ) : null}
        {authRequired && status !== "Pronto" && !authOpen && !useHttpFallback ? (
          <div className="mx-4 mt-3 rounded-xl border border-[var(--pkf-border)] bg-[var(--pkf-bg-panel)] p-3 text-sm text-[var(--pkf-muted)]">
            {status === "Token necessário" || status === "Token inválido" || !getToken() ? (
              <>
                Autenticação necessária. Abra a PKF com{" "}
                <code className="rounded bg-black/5 px-1">?token=SEU_PKF_AUTH_TOKEN</code> na URL ou{" "}
                <button
                  type="button"
                  className="font-medium text-[var(--pkf-accent)] underline"
                  onClick={() => setAuthOpen(true)}
                >
                  informe o token
                </button>
                .
              </>
            ) : (
              <>Conectando ao servidor… ({status})</>
            )}
          </div>
        ) : null}
        {useHttpFallback ? (
          <div className="mx-4 mt-3 rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">
            Chat via HTTP (WebSocket bloqueado neste navegador). Progresso em tempo real só após reconectar.{" "}
            <button type="button" className="font-medium underline" onClick={retryWebSocket}>
              Reconectar WebSocket
            </button>
          </div>
        ) : null}
        {progress ? (
          <div className="mx-4 mt-3 rounded-xl bg-[var(--pkf-accent)]/10 px-4 py-2 text-sm text-[var(--pkf-accent)]" aria-live="polite">
            {progress}
          </div>
        ) : null}

        <div className={`flex min-h-0 flex-1 ${previewOpen || showSpecPanel ? "flex-col lg:flex-row" : ""}`}>
          <main id="main-chat" className="min-h-0 flex-1 overflow-auto" tabIndex={0}>
            <MessageList messages={messages} thinking={thinking} />
          </main>

          {showSpecPanel ? (
            <SpecPanel
              spec={specPreview}
              specName={session.active_spec}
              onApproved={() => {
                setSpecPreview((s) => (s ? { ...s, status: "approved" } : s));
                setPanel("project");
              }}
            />
          ) : null}

          {previewOpen && previewSrc ? (
            <aside className="flex min-h-[40vh] flex-1 flex-col border-t border-[var(--pkf-border)] lg:max-w-[50%] lg:border-l lg:border-t-0">
              <header className="flex items-center justify-between border-b border-[var(--pkf-border)] px-4 py-2 text-sm">
                <strong>Preview</strong>
                <button type="button" aria-label="Fechar preview" className="h-10 w-10" onClick={() => setPreviewOpen(false)}>
                  ✕
                </button>
              </header>
              <iframe
                title="Preview do projeto"
                src={previewSrc}
                className="min-h-0 flex-1 bg-white"
                sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
              />
            </aside>
          ) : null}
        </div>

        <Composer busy={busy} onSend={sendMessage} />
      </div>
    </div>
  );
}
