import { useEffect, useRef, useState } from "react";
import type { ChatItem, ProjectItem, TaskNode } from "../types";
import { TaskTree } from "./TaskTree";

type Props = {
  open: boolean;
  onClose: () => void;
  projectName: string;
  tasks: TaskNode[];
  changes: { path: string; action: string }[];
  onNewProject: () => void;
  database: boolean;
  phase?: string;
  model?: string;
  chats: ChatItem[];
  projects: ProjectItem[];
  onSelectChat: (id: string) => void;
  onDeleteChat: (id: string) => void;
  onAttachChat: (chatId: string, projectSlug: string | null) => void;
  onSelectProject: (slug: string) => void;
  onDeleteProject: (slug: string) => void;
  onRenameProject: (slug: string, name: string) => void;
  onNewChat: () => void;
};

function ProjectRow({
  project,
  onSelect,
  onDelete,
  onRename,
}: {
  project: ProjectItem;
  onSelect: (slug: string) => void;
  onDelete: (project: ProjectItem) => void;
  onRename: (slug: string, name: string) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(project.name);
  const menuRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setDraft(project.name);
  }, [project.name]);

  useEffect(() => {
    if (!menuOpen) return;
    function onPointerDown(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [menuOpen]);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  function commitRename() {
    const next = draft.trim();
    setEditing(false);
    if (next && next !== project.name) onRename(project.slug, next);
    else setDraft(project.name);
  }

  return (
    <li
      className={`relative flex items-center gap-1 rounded-lg border px-2 py-2 text-xs ${
        project.is_active ? "border-[var(--pkf-accent)]/50 bg-[var(--pkf-bg-primary)]" : "border-[var(--pkf-border)]"
      }`}
    >
      {editing ? (
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commitRename}
          onKeyDown={(e) => {
            if (e.key === "Enter") commitRename();
            if (e.key === "Escape") {
              setDraft(project.name);
              setEditing(false);
            }
          }}
          className="pkf-input min-w-0 flex-1 text-xs font-medium"
          aria-label="Renomear projeto"
        />
      ) : (
        <button
          type="button"
          className="pkf-btn-ghost min-w-0 flex-1 truncate text-left font-medium"
          onClick={() => onSelect(project.slug)}
        >
          {project.name}
        </button>
      )}
      <div ref={menuRef} className="relative shrink-0">
        <button
          type="button"
          aria-label={`Ações do projeto ${project.name}`}
          aria-expanded={menuOpen}
          aria-haspopup="menu"
          className="pkf-btn-icon grid h-7 w-7 place-items-center rounded-lg text-[var(--pkf-muted)]"
          onClick={() => setMenuOpen((open) => !open)}
        >
          ⋮
        </button>
        {menuOpen ? (
          <div
            role="menu"
            className="absolute right-0 top-full z-40 mt-1 min-w-[8.5rem] rounded-lg border border-[var(--pkf-border)] bg-[var(--pkf-bg-panel)] py-1 shadow-lg"
          >
            <button
              type="button"
              role="menuitem"
              className="pkf-menu-item block w-full px-3 py-1.5 text-left text-xs"
              onClick={() => {
                setMenuOpen(false);
                setEditing(true);
              }}
            >
              Renomear
            </button>
            <button
              type="button"
              role="menuitem"
              className="pkf-menu-item block w-full px-3 py-1.5 text-left text-xs text-red-300 hover:bg-red-950/30"
              onClick={() => {
                setMenuOpen(false);
                onDelete(project);
              }}
            >
              Excluir
            </button>
          </div>
        ) : null}
      </div>
    </li>
  );
}

export function Sidebar({
  open,
  onClose,
  projectName,
  tasks,
  changes,
  onNewProject,
  database,
  phase,
  model,
  chats,
  projects,
  onSelectChat,
  onDeleteChat,
  onAttachChat,
  onSelectProject,
  onDeleteProject,
  onRenameProject,
  onNewChat,
}: Props) {
  if (!open) return null;

  function handleDeleteProject(project: ProjectItem) {
    if (!window.confirm(`Excluir o projeto "${project.name}" e todos os arquivos?`)) return;
    onDeleteProject(project.slug);
  }

  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-20 bg-black/60 md:hidden"
        aria-label="Fechar painel"
        onClick={onClose}
      />
      <aside className="fixed inset-y-0 left-14 z-30 flex w-72 flex-col gap-4 overflow-hidden border-r border-[var(--pkf-border)] bg-[var(--pkf-bg-panel)] p-5 md:static md:z-0">
        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          <section className="mb-5">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-[11px] font-semibold uppercase tracking-wider text-[var(--pkf-muted)]">Chats</h2>
              <button
                type="button"
                onClick={onNewChat}
                className="rounded px-2 py-1 text-[11px] text-[var(--pkf-accent)] hover:bg-[var(--pkf-bg-primary)]"
              >
                + Novo
              </button>
            </div>
            <ul className="space-y-1">
              {chats.length ? (
                chats.map((chat) => (
                  <li
                    key={chat.id}
                    className={`rounded-lg border px-2 py-2 text-xs ${
                      chat.is_active ? "border-[var(--pkf-accent)]/50 bg-[var(--pkf-bg-primary)]" : "border-[var(--pkf-border)]"
                    }`}
                  >
                    <button type="button" className="w-full text-left" onClick={() => onSelectChat(chat.id)}>
                      <span className="line-clamp-2 font-medium">{chat.title || "Chat"}</span>
                      {chat.project_slug ? (
                        <span className="mt-1 block text-[10px] text-[var(--pkf-text-dim)]">📎 {chat.project_slug}</span>
                      ) : null}
                    </button>
                    <div className="mt-2 flex flex-wrap gap-1">
                      <select
                        className="max-w-full flex-1 rounded border border-[var(--pkf-border)] bg-[var(--pkf-bg-primary)] px-1 py-0.5 text-[10px]"
                        value={chat.project_slug || ""}
                        onChange={(e) => onAttachChat(chat.id, e.target.value || null)}
                        aria-label="Anexar projeto ao chat"
                      >
                        <option value="">Sem projeto</option>
                        {projects.map((p) => (
                          <option key={p.slug} value={p.slug}>
                            {p.name}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        className="rounded border border-[var(--pkf-border)] px-2 py-0.5 text-[10px] hover:border-red-500/50"
                        onClick={() => onDeleteChat(chat.id)}
                      >
                        Excluir
                      </button>
                    </div>
                  </li>
                ))
              ) : (
                <li className="text-xs text-[var(--pkf-text-dim)]">Nenhum chat</li>
              )}
            </ul>
          </section>

          <section className="mb-5">
            <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--pkf-muted)]">Projetos</h2>
            <ul className="space-y-1">
              {projects.length ? (
                projects.map((project) => (
                  <ProjectRow
                    key={project.slug}
                    project={project}
                    onSelect={onSelectProject}
                    onDelete={handleDeleteProject}
                    onRename={onRenameProject}
                  />
                ))
              ) : (
                <li className="text-xs text-[var(--pkf-text-dim)]">Nenhum projeto</li>
              )}
            </ul>
            <button type="button" onClick={onNewProject} className="pkf-btn-secondary mt-2 min-h-9 w-full text-sm">
              Novo projeto
            </button>
          </section>

          <div className="mb-4">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--pkf-muted)]">Ativo</p>
            <p className="mt-1 text-sm font-medium">{projectName}</p>
            {phase ? <p className="mt-1 text-xs text-[var(--pkf-muted)]">Fase: {phase}</p> : null}
            {model ? <p className="mt-0.5 truncate font-mono text-[10px] text-[var(--pkf-muted)]">{model}</p> : null}
          </div>

          <section className="mb-4">
            <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--pkf-muted)]">Tarefas</h2>
            <TaskTree tasks={tasks} />
          </section>

          <section>
            <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--pkf-muted)]">Alterações</h2>
            <ul className="max-h-32 overflow-auto font-mono text-[11px] text-[var(--pkf-muted)]">
              {changes.length ? (
                changes.map((c, i) => (
                  <li key={i} className="border-b border-[var(--pkf-border)] py-1.5">
                    {c.path} <span className="text-[var(--pkf-text-dim)]">({c.action})</span>
                  </li>
                ))
              ) : (
                <li>—</li>
              )}
            </ul>
          </section>
        </div>

        {database ? <p className="text-[10px] text-[var(--pkf-accent)]/80">PostgreSQL</p> : null}
      </aside>
    </>
  );
}
