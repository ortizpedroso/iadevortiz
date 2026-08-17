import { useCallback, useEffect, useRef, useState } from "react";
import { AuthModal } from "./components/AuthModal";
import { Composer } from "./components/Composer";
import { IconRail } from "./components/IconRail";
import { MessageList } from "./components/MessageList";
import { Sidebar } from "./components/Sidebar";
import { SpecPanel } from "./components/SpecPanel";
import { authHeaders, getToken, previewUrl, wsUrl } from "./lib/api";
import type { ChatItem, Message, ProjectItem, SessionSnapshot, SpecPreview, TaskNode, WsEvent } from "./types";

export default function App() {
  const [authRequired, setAuthRequired] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const [panel, setPanel] = useState<"project" | "spec" | null>("project");
  const [messages, setMessages] = useState<Message[]>([]);
  const [session, setSession] = useState<SessionSnapshot>({});
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

  const applySession = useCallback((data: SessionSnapshot, replaceSpec = false) => {
    setSession((s) => ({ ...s, ...data }));
    if (data.tasks) setTasks(data.tasks);
    if (data.spec_preview) {
      setSpecPreview(data.spec_preview);
      if (data.spec_preview.status === "pending_approval") setPanel("spec");
    } else if (replaceSpec) {
      setSpecPreview(null);
      setPanel("project");
    }
    if (data.project_preview?.available && data.project_preview.path) {
      setPreviewSrc(previewUrl(data.project_preview.path));
    } else if (replaceSpec) {
      setPreviewSrc("");
      setPreviewOpen(false);
    }
    if (data.active_agent) setActiveAgent(data.active_agent);
  }, []);

  const connect = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) return;
    const ws = new WebSocket(wsUrl());
    socketRef.current = ws;
    ws.onopen = () => setStatus("Pronto");
    ws.onclose = () => {
      setStatus("Reconectando…");
      setTimeout(connect, 1500);
    };
    ws.onmessage = (ev) => {
      const event: WsEvent = JSON.parse(ev.data);
      if (event.type === "session") {
        applySession(event as SessionSnapshot);
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
        setMessages((m) => [...m, { role: "error", content: event.content || "Erro" }]);
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
        applySession(event as SessionSnapshot);
        loadChanges();
      }
    };
  }, [applySession, loadChanges]);

  useEffect(() => {
    async function boot() {
      const healthRes = await fetch("/api/health");
      if (healthRes.ok) {
        const info = await healthRes.json();
        setAuthRequired(!!info.auth_required);
        if (info.auth_required && !getToken()) {
          setAuthOpen(true);
          return;
        }
      }
      try {
        const res = await fetch("/api/session", { headers: authHeaders() });
        if (res.status === 401) {
          setAuthOpen(true);
          return;
        }
        if (res.ok) {
          const data = await res.json();
          applySession(data.session);
          setMessages(data.messages || []);
          applyLibrary(data.library);
        }
      } catch {
        /* offline bootstrap */
      }
      loadLibrary();
      loadChanges();
      connect();
    }
    boot();
    return () => socketRef.current?.close();
  }, [applySession, applyLibrary, connect, loadChanges, loadLibrary]);

  function handleAuth(token: string) {
    sessionStorage.setItem("pkf_token", token);
    setAuthOpen(false);
    location.reload();
  }

  function sendMessage(text: string) {
    const ws = socketRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setMessages((m) => [...m, { role: "error", content: "Ainda conectando… tente de novo." }]);
      connect();
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
    setSession({});
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
    if (data.session) applySession(data.session);
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
    if (!res.ok) return;
    const data = await res.json();
    applyLibrary(data.library);
    await loadLibrary();
    const sessionRes = await fetch("/api/session", { headers: authHeaders() });
    if (sessionRes.ok) {
      const payload = await sessionRes.json();
      setMessages(payload.messages || []);
      applySession(payload.session, true);
      loadChanges();
    }
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
    if (!res.ok) return;
    const data = await res.json();
    applyLibrary(data.library);
    const sessionRes = await fetch("/api/session", { headers: authHeaders() });
    if (sessionRes.ok) {
      const payload = await sessionRes.json();
      applySession(payload.session, true);
      loadChanges();
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

  const projectName =
    session.project_name && session.project_name !== "(sem projeto ativo)"
      ? session.project_name
      : "Nenhum ainda";

  const showSpecPanel =
    panel === "spec" && specPreview && specPreview.status !== "approved";

  return (
    <div className="flex h-full min-h-dvh">
      <AuthModal open={authOpen && authRequired} onSubmit={handleAuth} />

      <a
        href="#main-chat"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:rounded focus:bg-[var(--pkf-accent)] focus:px-3 focus:py-2 focus:text-[var(--pkf-bg-primary)]"
      >
        Ir ao chat
      </a>

      <IconRail
        panel={panel}
        onPanel={setPanel}
        hasSpec={!!specPreview && specPreview.status !== "approved"}
        previewAvailable={!!session.project_preview?.available}
        onPreview={() => setPreviewOpen(true)}
      />

      <Sidebar
        open={panel === "project"}
        onClose={() => setPanel(null)}
        projectName={projectName}
        tasks={tasks}
        changes={changes}
        onNewProject={newProject}
        database={!!session.database}
        phase={session.phase}
        model={session.model}
        chats={chats}
        projects={projects}
        onSelectChat={selectChat}
        onDeleteChat={deleteChat}
        onAttachChat={attachChat}
        onSelectProject={selectProject}
        onDeleteProject={deleteProject}
        onRenameProject={renameProject}
        onNewChat={newChat}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex min-h-12 items-center gap-3 border-b border-[var(--pkf-border)] px-4">
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
                  busy ? "bg-[var(--pkf-accent)]" : status === "Pronto" ? "bg-emerald-500" : "bg-[var(--pkf-text-dim)]"
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
          {session.project_preview?.available ? (
            <div className="ml-auto flex gap-2">
              <button
                type="button"
                className="hidden min-h-9 rounded-lg border border-[#2e2e2e] px-3 text-xs font-medium hover:border-[#d97757]/50 sm:inline-flex sm:items-center"
                onClick={() => setPreviewOpen((v) => !v)}
              >
                {previewOpen ? "Ocultar preview" : "Preview"}
              </button>
              <a
                href={previewSrc}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex min-h-9 items-center rounded-lg border border-[#2e2e2e] px-3 text-xs font-medium hover:border-[#d97757]/50"
              >
                Abrir ↗
              </a>
            </div>
          ) : null}
        </header>

        {session.provider_error ? (
          <div className="mx-4 mt-3 rounded-xl border border-amber-600/40 bg-amber-950/20 p-3 text-sm text-amber-100">
            {session.provider_error}
          </div>
        ) : null}
        {progress ? (
          <div className="mx-4 mt-3 rounded-xl bg-[#d97757]/10 px-4 py-2 text-sm text-[#d97757]" aria-live="polite">
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
            <aside className="flex min-h-[40vh] flex-1 flex-col border-t border-[#2e2e2e] lg:max-w-[50%] lg:border-l lg:border-t-0">
              <header className="flex items-center justify-between border-b border-[#2e2e2e] px-4 py-2 text-sm">
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
