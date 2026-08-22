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
  onRenameChat: (id: string, title: string) => void;
  onAttachChat: (chatId: string, projectSlug: string | null) => void;
  onSelectProject: (slug: string) => void;
  onDeleteProject: (slug: string) => void;
  onBulkDeleteProjects: (slugs: string[], deleteAll?: boolean) => void;
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
  selectMode,
  selected,
  onToggleSelect,
}: {
  project: ProjectItem;
  onSelect: (slug: string) => void;
  onDelete: (project: ProjectItem) => void;
  onRename: (slug: string, name: string) => void;
  onPin: (slug: string, pinned: boolean) => void;
  selectMode?: boolean;
  selected?: boolean;
  onToggleSelect?: (slug: string) => void;
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
        className={`flex items-center gap-2 rounded-xl px-2.5 py-2.5 transition ${
          project.is_active
            ? "bg-[var(--pkf-bg-panel)] text-[var(--pkf-text)] ring-1 ring-[var(--pkf-border-soft)]"
            : "text-[var(--pkf-muted)] hover:bg-[var(--pkf-bg-panel)]/70 hover:text-[var(--pkf-text)]"
        }`}
      >
        {selectMode ? (
          <input
            type="checkbox"
            checked={!!selected}
            onChange={() => onToggleSelect?.(project.slug)}
            aria-label={`Selecionar ${label}`}
            className="h-4 w-4 shrink-0 rounded border-[var(--pkf-border)] accent-[var(--pkf-accent)]"
          />
        ) : null}
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
            onClick={() => (selectMode ? onToggleSelect?.(project.slug) : onSelect(project.slug))}
          >
            {label}
          </button>
        )}
        <div ref={menuRef} className="relative shrink-0">
          {!selectMode ? (
          <button
            type="button"
            aria-label={`Ações do projeto ${label}`}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-[var(--pkf-border-soft)] bg-[var(--pkf-bg-panel)] text-base leading-none text-[var(--pkf-muted)] hover:border-[var(--pkf-border)] hover:text-[var(--pkf-text)]"
            onClick={() => setMenuOpen((open) => !open)}
          >
            ⋯
          </button>
          ) : null}
          {menuOpen && !selectMode ? (
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
                className="pkf-menu-item block w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50"
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

function ChatRow({
  chat,
  projects,
  onSelect,
  onDelete,
  onRename,
  onAttach,
}: {
  chat: ChatItem;
  projects: ProjectItem[];
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onAttach: (chatId: string, projectSlug: string | null) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(chat.title || "Chat");
  const menuRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const label = chat.title || "Chat";

  useEffect(() => {
    setDraft(chat.title || "Chat");
  }, [chat.title]);

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
    if (next && next !== label) onRename(chat.id, next);
    else setDraft(label);
  }

  return (
    <li className="group relative">
      <div
        className={`flex items-center gap-2 rounded-xl px-2.5 py-2.5 transition ${
          chat.is_active
            ? "bg-[var(--pkf-bg-panel)] text-[var(--pkf-text)] ring-1 ring-[var(--pkf-border-soft)] shadow-sm"
            : "text-[var(--pkf-muted)] hover:bg-[var(--pkf-bg-panel)]/80 hover:text-[var(--pkf-text)]"
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
                setDraft(label);
                setEditing(false);
              }
            }}
            className="pkf-input min-w-0 flex-1 text-sm"
            aria-label="Renomear chat"
          />
        ) : (
          <button
            type="button"
            className="min-w-0 flex-1 truncate text-left text-sm"
            onClick={() => onSelect(chat.id)}
          >
            <span className="line-clamp-2">{label}</span>
          </button>
        )}
        <div ref={menuRef} className="relative shrink-0">
          <button
            type="button"
            aria-label={`Ações do chat ${label}`}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-[var(--pkf-border-soft)] bg-[var(--pkf-bg-panel)] text-base leading-none text-[var(--pkf-muted)] hover:border-[var(--pkf-border)] hover:text-[var(--pkf-text)]"
            onClick={(e) => {
              e.stopPropagation();
              setMenuOpen((open) => !open);
            }}
          >
            ⋯
          </button>
          {menuOpen ? (
            <div
              role="menu"
              className="absolute right-0 top-full z-40 mt-1 min-w-[9.5rem] rounded-xl border border-[var(--pkf-border)] bg-[var(--pkf-bg-elevated)] py-1 shadow-2xl"
            >
              {projects.length ? (
                <div className="border-b border-[var(--pkf-border-soft)] px-3 py-2">
                  <label className="mb-1 block text-[10px] font-medium uppercase tracking-wide text-[var(--pkf-text-dim)]">
                    Vincular projeto
                  </label>
                  <select
                    className="pkf-input w-full text-xs"
                    value={chat.project_slug || ""}
                    onChange={(e) => {
                      onAttach(chat.id, e.target.value || null);
                      setMenuOpen(false);
                    }}
                    aria-label="Vincular projeto"
                  >
                    <option value="">Sem projeto</option>
                    {projects.map((p) => (
                      <option key={p.slug} value={p.slug}>
                        {p.name || p.slug}
                      </option>
                    ))}
                  </select>
                </div>
              ) : null}
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
                className="pkf-menu-item block w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50"
                onClick={() => {
                  setMenuOpen(false);
                  onDelete(chat.id);
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
  onRenameChat,
  onAttachChat,
  onSelectProject,
  onDeleteProject,
  onBulkDeleteProjects,
  onRenameProject,
  onPinProject,
  onNewChat,
}: Props) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [projectSelectMode, setProjectSelectMode] = useState(false);
  const [selectedSlugs, setSelectedSlugs] = useState<Set<string>>(new Set());

  if (!open) return null;

  function toggleProjectSlug(slug: string) {
    setSelectedSlugs((current) => {
      const next = new Set(current);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  function exitProjectSelectMode() {
    setProjectSelectMode(false);
    setSelectedSlugs(new Set());
  }

  function handleBulkDeleteSelected() {
    const slugs = Array.from(selectedSlugs);
    if (!slugs.length) return;
    const names = projects
      .filter((p) => selectedSlugs.has(p.slug))
      .map((p) => p.name || p.slug)
      .join(", ");
    if (!window.confirm(`Excluir ${slugs.length} projeto(s)?\n\n${names}\n\nTodos os arquivos serão removidos.`)) {
      return;
    }
    onBulkDeleteProjects(slugs);
    exitProjectSelectMode();
  }

  function handleDeleteAllProjects() {
    if (!projects.length) return;
    if (
      !window.confirm(
        `Excluir TODOS os ${projects.length} projetos?\n\nEsta ação não pode ser desfeita.`
      )
    ) {
      return;
    }
    onBulkDeleteProjects([], true);
    exitProjectSelectMode();
  }

  function handleDeleteProject(project: ProjectItem) {
    if (!window.confirm(`Excluir o projeto "${project.name || project.slug}" e todos os arquivos?`)) return;
    onDeleteProject(project.slug);
  }

  const showBuildMeta = ready && busy && (phase || model || tasks.length > 0);

  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-20 bg-black/30 md:hidden"
        aria-label="Fechar painel"
        onClick={onClose}
      />
      <aside className="fixed inset-y-0 left-0 z-30 flex w-[18rem] flex-col border-r border-[var(--pkf-border-soft)] bg-[var(--pkf-bg-sidebar)] md:static md:z-0">
        <div className="flex items-center justify-between border-b border-[var(--pkf-border-soft)] px-4 py-4">
          <div className="flex items-center gap-2.5">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--pkf-accent)] text-sm font-bold text-[#1a1917]">
              P
            </div>
            <div>
              <span className="block text-sm font-semibold text-[var(--pkf-text)]">PKF</span>
              <span className="block text-[10px] text-[var(--pkf-text-dim)]">Assistente de código</span>
            </div>
          </div>
          <button
            type="button"
            onClick={onNewChat}
            className="rounded-xl bg-[var(--pkf-bg-panel)] px-3 py-2 text-xs font-medium text-[var(--pkf-text)] ring-1 ring-[var(--pkf-border-soft)] transition hover:bg-[var(--pkf-bg-hover)]"
          >
            + Chat
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
          <section className="mb-6">
            <div className="mb-2 flex items-center justify-between px-2">
              <h2 className="text-xs font-medium text-[var(--pkf-text-dim)]">Projetos</h2>
              {ready && projects.length > 0 ? (
                projectSelectMode ? (
                  <button
                    type="button"
                    className="text-[10px] text-[var(--pkf-muted)] hover:text-[var(--pkf-text)]"
                    onClick={exitProjectSelectMode}
                  >
                    Cancelar
                  </button>
                ) : (
                  <button
                    type="button"
                    className="text-[10px] text-[var(--pkf-accent)] hover:underline"
                    onClick={() => setProjectSelectMode(true)}
                  >
                    Selecionar
                  </button>
                )
              ) : null}
            </div>
            {!ready ? (
              <p className="px-2 text-sm text-[var(--pkf-text-dim)]">Carregando…</p>
            ) : projects.length ? (
              <>
                {projectSelectMode ? (
                  <div className="mb-2 flex items-center gap-2 px-2">
                    <input
                      type="checkbox"
                      checked={selectedSlugs.size === projects.length}
                      onChange={(e) => {
                        if (e.target.checked) setSelectedSlugs(new Set(projects.map((p) => p.slug)));
                        else setSelectedSlugs(new Set());
                      }}
                      aria-label="Selecionar todos os projetos"
                      className="h-4 w-4 rounded border-[var(--pkf-border)] accent-[var(--pkf-accent)]"
                    />
                    <span className="text-[10px] text-[var(--pkf-text-dim)]">Todos</span>
                  </div>
                ) : null}
                <ul className="space-y-0.5">
                  {projects.map((project) => (
                    <ProjectRow
                      key={project.slug}
                      project={project}
                      onSelect={onSelectProject}
                      onDelete={handleDeleteProject}
                      onRename={onRenameProject}
                      onPin={onPinProject}
                      selectMode={projectSelectMode}
                      selected={selectedSlugs.has(project.slug)}
                      onToggleSelect={toggleProjectSlug}
                    />
                  ))}
                </ul>
                {projectSelectMode ? (
                  <div className="mt-3 space-y-2">
                    <button
                      type="button"
                      disabled={selectedSlugs.size === 0}
                      onClick={handleBulkDeleteSelected}
                      className="w-full rounded-xl border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 transition hover:bg-red-100 disabled:opacity-40"
                    >
                      Excluir selecionados ({selectedSlugs.size})
                    </button>
                    <button
                      type="button"
                      onClick={handleDeleteAllProjects}
                      className="w-full rounded-xl border border-[var(--pkf-border)] px-3 py-2 text-xs text-[var(--pkf-muted)] hover:text-red-700"
                    >
                      Excluir todos ({projects.length})
                    </button>
                  </div>
                ) : null}
              </>
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
                  <ChatRow
                    key={chat.id}
                    chat={chat}
                    projects={projects}
                    onSelect={onSelectChat}
                    onDelete={onDeleteChat}
                    onRename={onRenameChat}
                    onAttach={onAttachChat}
                  />
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
