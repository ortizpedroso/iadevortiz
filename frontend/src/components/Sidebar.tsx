import { useEffect, useRef, useState } from "react";
import type { ChatItem, ProjectItem, TaskNode } from "../types";
import { TaskTree } from "./TaskTree";

type Props = {
  open: boolean;
  ready: boolean;
  onClose: () => void;
  projectName: string;
  tasks: TaskNode[];
  changes: { path: string; action: string }[];
  onNewProject: () => void;
  database: boolean;
  phase?: string;
  model?: string;
  busy?: boolean;
  chats: ChatItem[];
  projects: ProjectItem[];
  onSelectChat: (id: string) => void;
  onDeleteChat: (id: string) => void;
  onAttachChat: (chatId: string, projectSlug: string | null) => void;
  onSelectProject: (slug: string) => void;
  onDeleteProject: (slug: string) => void;
  onRenameProject: (slug: string, name: string) => void;
  onPinProject: (slug: string, pinned: boolean) => void;
  onNewChat: () => void;
};

function ProjectRow({
  project,
  onSelect,
  onDelete,
  onRename,
  onPin,
}: {
  project: ProjectItem;
  onSelect: (slug: string) => void;
  onDelete: (project: ProjectItem) => void;
  onRename: (slug: string, name: string) => void;
  onPin: (slug: string, pinned: boolean) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(project.name || project.slug);
  const menuRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setDraft(project.name || project.slug);
  }, [project.name, project.slug]);

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
    const current = project.name || project.slug;
    if (next && next !== current) onRename(project.slug, next);
    else setDraft(current);
  }

  const label = project.name || project.slug;

  return (
    <li className="group relative">
      <div
        className={`flex items-center gap-1 rounded-xl px-2 py-2 transition ${
          project.is_active
            ? "bg-[var(--pkf-bg-hover)] text-[var(--pkf-text)]"
            : "text-[var(--pkf-muted)] hover:bg-[var(--pkf-bg-hover)] hover:text-[var(--pkf-text)]"
        }`}
      >
        {project.pinned ? (
          <span className="shrink-0 text-[10px] text-[var(--pkf-accent)]" aria-hidden>
            📌
          </span>
        ) : null}
        {editing ? (
          <input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commitRename}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitRename();
              if (e.key === "Escape") {
                setDraft(label);
                setEditing(false);
              }
            }}
            className="pkf-input min-w-0 flex-1 text-sm"
            aria-label="Renomear projeto"
          />
        ) : (
          <button
            type="button"
            className="min-w-0 flex-1 truncate text-left text-sm"
            onClick={() => onSelect(project.slug)}
          >
            {label}
          </button>
        )}
        <div ref={menuRef} className="relative shrink-0">
          <button
            type="button"
            aria-label={`Ações do projeto ${label}`}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            className="grid h-8 w-8 place-items-center rounded-lg text-[var(--pkf-muted)] opacity-0 transition group-hover:opacity-100 hover:bg-[var(--pkf-border)]/60 focus:opacity-100"
            onClick={() => setMenuOpen((open) => !open)}
          >
            ⋯
          </button>
          {menuOpen ? (
            <div
              role="menu"
              className="absolute right-0 top-full z-40 mt-1 min-w-[9.5rem] rounded-xl border border-[var(--pkf-border)] bg-[var(--pkf-bg-elevated)] py-1 shadow-2xl"
            >
              <button
                type="button"
                role="menuitem"
                className="pkf-menu-item block w-full px-3 py-2 text-left text-sm"
                onClick={() => {
                  setMenuOpen(false);
                  onPin(project.slug, !project.pinned);
                }}
              >
                {project.pinned ? "Desafixar" : "Fixar"}
              </button>
              <button
                type="button"
                role="menuitem"
                className="pkf-menu-item block w-full px-3 py-2 text-left text-sm"
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
                className="pkf-menu-item block w-full px-3 py-2 text-left text-sm text-red-300 hover:bg-red-950/30"
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
      </div>
    </li>
  );
}

export function Sidebar({
  open,
  ready,
  onClose,
  projectName,
  tasks,
  changes,
  onNewProject,
  database,
  phase,
  model,
  busy,
  chats,
  projects,
  onSelectChat,
  onDeleteChat,
  onAttachChat,
  onSelectProject,
  onDeleteProject,
  onRenameProject,
  onPinProject,
  onNewChat,
}: Props) {
  const [detailsOpen, setDetailsOpen] = useState(false);

  if (!open) return null;

  function handleDeleteProject(project: ProjectItem) {
    if (!window.confirm(`Excluir o projeto "${project.name || project.slug}" e todos os arquivos?`)) return;
    onDeleteProject(project.slug);
  }

  const showBuildMeta = ready && busy && (phase || model || tasks.length > 0);

  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-20 bg-black/60 md:hidden"
        aria-label="Fechar painel"
        onClick={onClose}
      />
      <aside className="fixed inset-y-0 left-0 z-30 flex w-[17.5rem] flex-col border-r border-[var(--pkf-border)] bg-[var(--pkf-bg-sidebar)] md:static md:z-0">
        <div className="flex items-center justify-between border-b border-[var(--pkf-border)] px-4 py-4">
          <div className="flex items-center gap-2">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-[var(--pkf-accent)]/15 text-sm font-bold text-[var(--pkf-accent)]">
              P
            </div>
            <span className="text-sm font-medium text-[var(--pkf-text)]">PKF</span>
          </div>
          <button
            type="button"
            onClick={onNewChat}
            className="rounded-lg border border-[var(--pkf-border)] px-3 py-1.5 text-xs font-medium text-[var(--pkf-text)] transition hover:bg-[var(--pkf-bg-hover)]"
          >
            Novo chat
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
          <section className="mb-6">
            <h2 className="mb-2 px-2 text-xs font-medium text-[var(--pkf-text-dim)]">Projetos</h2>
            {!ready ? (
              <p className="px-2 text-sm text-[var(--pkf-text-dim)]">Carregando…</p>
            ) : projects.length ? (
              <ul className="space-y-0.5">
                {projects.map((project) => (
                  <ProjectRow
                    key={project.slug}
                    project={project}
                    onSelect={onSelectProject}
                    onDelete={handleDeleteProject}
                    onRename={onRenameProject}
                    onPin={onPinProject}
                  />
                ))}
              </ul>
            ) : (
              <p className="px-2 text-sm text-[var(--pkf-text-dim)]">Nenhum projeto ainda</p>
            )}
            <button
              type="button"
              onClick={onNewProject}
              className="mt-3 w-full rounded-xl border border-dashed border-[var(--pkf-border)] px-3 py-2 text-sm text-[var(--pkf-muted)] transition hover:border-[var(--pkf-accent)]/40 hover:text-[var(--pkf-text)]"
            >
              + Novo projeto
            </button>
          </section>

          <section className="mb-4">
            <h2 className="mb-2 px-2 text-xs font-medium text-[var(--pkf-text-dim)]">Conversas</h2>
            <ul className="space-y-0.5">
              {ready && chats.length ? (
                chats.map((chat) => (
                  <li key={chat.id}>
                    <button
                      type="button"
                      className={`w-full rounded-xl px-3 py-2 text-left text-sm transition ${
                        chat.is_active
                          ? "bg-[var(--pkf-bg-hover)] text-[var(--pkf-text)]"
                          : "text-[var(--pkf-muted)] hover:bg-[var(--pkf-bg-hover)] hover:text-[var(--pkf-text)]"
                      }`}
                      onClick={() => onSelectChat(chat.id)}
                    >
                      <span className="line-clamp-2">{chat.title || "Chat"}</span>
                    </button>
                    {chat.is_active ? (
                      <div className="mt-1 flex gap-1 px-2">
                        <select
                          className="min-w-0 flex-1 rounded-lg border border-[var(--pkf-border)] bg-[var(--pkf-bg-primary)] px-2 py-1 text-[10px] text-[var(--pkf-muted)]"
                          value={chat.project_slug || ""}
                          onChange={(e) => onAttachChat(chat.id, e.target.value || null)}
                          aria-label="Vincular projeto"
                        >
                          <option value="">Sem projeto</option>
                          {projects.map((p) => (
                            <option key={p.slug} value={p.slug}>
                              {p.name || p.slug}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          className="rounded-lg px-2 text-[10px] text-[var(--pkf-text-dim)] hover:text-red-300"
                          onClick={() => onDeleteChat(chat.id)}
                        >
                          Excluir
                        </button>
                      </div>
                    ) : null}
                  </li>
                ))
              ) : (
                <li className="px-2 text-sm text-[var(--pkf-text-dim)]">{ready ? "Nenhuma conversa" : "Carregando…"}</li>
              )}
            </ul>
          </section>

          {ready ? (
            <section className="border-t border-[var(--pkf-border)] pt-4">
              <p className="px-2 text-xs text-[var(--pkf-text-dim)]">Projeto ativo</p>
              <p className="px-2 pt-1 text-sm font-medium text-[var(--pkf-text)]">{projectName}</p>
              {showBuildMeta ? (
                <div className="mt-3 px-2">
                  <button
                    type="button"
                    className="text-xs text-[var(--pkf-accent)]"
                    onClick={() => setDetailsOpen((v) => !v)}
                  >
                    {detailsOpen ? "Ocultar detalhes" : "Ver detalhes do build"}
                  </button>
                  {detailsOpen ? (
                    <div className="mt-2 space-y-2">
                      {phase ? <p className="text-xs text-[var(--pkf-muted)]">Fase: {phase}</p> : null}
                      {model ? <p className="truncate font-mono text-[10px] text-[var(--pkf-muted)]">{model}</p> : null}
                      <TaskTree tasks={tasks} />
                      {changes.length ? (
                        <ul className="max-h-28 overflow-auto font-mono text-[10px] text-[var(--pkf-muted)]">
                          {changes.map((c, i) => (
                            <li key={i} className="border-b border-[var(--pkf-border)] py-1">
                              {c.path} ({c.action})
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </section>
          ) : null}
        </div>

        {database ? <p className="border-t border-[var(--pkf-border)] px-4 py-2 text-[10px] text-[var(--pkf-text-dim)]">PostgreSQL</p> : null}
      </aside>
    </>
  );
}
