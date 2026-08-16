import { useCallback, useEffect, useRef, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { Composer } from "./components/Composer";
import { MessageList } from "./components/MessageList";
import { authHeaders, getToken, previewUrl, wsUrl } from "./lib/api";
import type { Message, SessionSnapshot, TaskNode, WsEvent } from "./types";

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [session, setSession] = useState<SessionSnapshot>({});
  const [tasks, setTasks] = useState<TaskNode[]>([]);
  const [changes, setChanges] = useState<{ path: string; action: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [progress, setProgress] = useState("");
  const [status, setStatus] = useState("Conectando…");
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewSrc, setPreviewSrc] = useState("");
  const socketRef = useRef<WebSocket | null>(null);

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

  const applySession = useCallback(
    (data: SessionSnapshot) => {
      setSession((s) => ({ ...s, ...data }));
      if (data.tasks) setTasks(data.tasks);
      if (data.project_preview?.available && data.project_preview.path) {
        setPreviewSrc(previewUrl(data.project_preview.path));
      }
    },
    [],
  );

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
      if (event.type === "progress" || event.type === "task_progress") {
        setProgress(event.message || "");
        setThinking(true);
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
      if (!getToken() && (await fetch("/api/health")).ok) {
        const info = await (await fetch("/api/health")).json();
        if (info.auth_required) {
          const token = prompt("Informe o token de acesso da PKF:");
          if (token) {
            sessionStorage.setItem("pkf_token", token);
            location.reload();
          }
        }
      }
      try {
        const res = await fetch("/api/session", { headers: authHeaders() });
        if (res.ok) {
          const data = await res.json();
          applySession(data.session);
          setMessages(data.messages || []);
        }
      } catch {
        /* offline bootstrap */
      }
      loadChanges();
      connect();
    }
    boot();
    return () => socketRef.current?.close();
  }, [applySession, connect, loadChanges]);

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
    setSession({});
    setTasks([]);
    loadChanges();
  }

  const projectName =
    session.project_name && session.project_name !== "(sem projeto ativo)"
      ? session.project_name
      : "Nenhum ainda";

  return (
    <div className="flex h-full min-h-dvh">
      <a
        href="#main-chat"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:rounded focus:bg-emerald-500 focus:px-3 focus:py-2 focus:text-black"
      >
        Ir ao chat
      </a>
      <Sidebar
        open={sidebarOpen}
        onToggle={() => setSidebarOpen(false)}
        projectName={projectName}
        tasks={tasks}
        changes={changes}
        onNewProject={newProject}
        database={!!session.database}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex min-h-14 items-center gap-3 border-b border-slate-800 px-4">
          <button
            type="button"
            className="grid h-11 w-11 place-items-center rounded-lg md:hidden"
            aria-label="Abrir menu"
            onClick={() => setSidebarOpen(true)}
          >
            ☰
          </button>
          <div className="flex items-center gap-2 font-semibold" aria-live="polite">
            <span
              className={`h-2 w-2 rounded-full ${
                busy ? "bg-amber-400" : status === "Pronto" ? "bg-emerald-400" : "bg-slate-500"
              }`}
            />
            {busy ? "Trabalhando…" : status}
          </div>
          {session.project_preview?.available ? (
            <div className="ml-auto flex gap-2">
              <button
                type="button"
                className="min-h-11 rounded-lg border border-slate-600 px-3 text-sm font-medium hover:border-emerald-500"
                onClick={() => setPreviewOpen(true)}
              >
                Ver ao lado
              </button>
              <a
                href={previewSrc}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex min-h-11 items-center rounded-lg border border-slate-600 px-3 text-sm font-medium hover:border-emerald-500"
              >
                Abrir ↗
              </a>
            </div>
          ) : null}
        </header>

        {session.provider_error ? (
          <div className="mx-4 mt-3 rounded-lg border border-amber-600/50 bg-amber-950/30 p-3 text-sm text-amber-100">
            {session.provider_error}
          </div>
        ) : null}
        {progress ? (
          <div className="mx-4 mt-3 rounded-lg bg-emerald-500/10 px-4 py-2 text-sm text-emerald-100" aria-live="polite">
            {progress}
          </div>
        ) : null}

        <div className={`flex min-h-0 flex-1 ${previewOpen ? "flex-col lg:flex-row" : ""}`}>
          <main id="main-chat" className="min-h-0 flex-1 overflow-auto py-6" tabIndex={0}>
            <MessageList messages={messages} thinking={thinking} />
          </main>
          {previewOpen && previewSrc ? (
            <aside className="flex min-h-[40vh] flex-1 flex-col border-t border-slate-800 lg:border-l lg:border-t-0">
              <header className="flex items-center justify-between border-b border-slate-800 px-4 py-2 text-sm">
                <strong>Preview do projeto</strong>
                <button type="button" aria-label="Fechar preview" className="h-11 w-11" onClick={() => setPreviewOpen(false)}>
                  ✕
                </button>
              </header>
              <iframe title="Preview do projeto" src={previewSrc} className="min-h-0 flex-1 bg-white" sandbox="allow-scripts allow-same-origin allow-forms allow-popups" />
            </aside>
          ) : null}
        </div>

        <Composer busy={busy} onSend={sendMessage} />
      </div>
    </div>
  );
}
