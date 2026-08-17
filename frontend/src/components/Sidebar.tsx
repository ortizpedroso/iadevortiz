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
  onNewChat: () => void;
};

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
  onNewChat,
}: Props) {
  if (!open) return null;

  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-20 bg-black/60 md:hidden"
        aria-label="Fechar painel"
        onClick={onClose}
      />
      <aside className="fixed inset-y-0 left-14 z-30 flex w-72 flex-col gap-4 overflow-hidden border-r border-[#2e2e2e] bg-[#212121] p-5 md:static md:z-0">
        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          <section className="mb-5">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-[11px] font-semibold uppercase tracking-wider text-[#9b9b9b]">Chats</h2>
              <button
                type="button"
                onClick={onNewChat}
                className="rounded px-2 py-1 text-[11px] text-[#d97757] hover:bg-[#191919]"
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
                      chat.is_active ? "border-[#d97757]/50 bg-[#191919]" : "border-[#2e2e2e]"
                    }`}
                  >
                    <button type="button" className="w-full text-left" onClick={() => onSelectChat(chat.id)}>
                      <span className="line-clamp-2 font-medium">{chat.title || "Chat"}</span>
                      {chat.project_slug ? (
                        <span className="mt-1 block text-[10px] text-[#666]">📎 {chat.project_slug}</span>
                      ) : null}
                    </button>
                    <div className="mt-2 flex flex-wrap gap-1">
                      <select
                        className="max-w-full flex-1 rounded border border-[#2e2e2e] bg-[#191919] px-1 py-0.5 text-[10px]"
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
                        className="rounded border border-[#2e2e2e] px-2 py-0.5 text-[10px] hover:border-red-500/50"
                        onClick={() => onDeleteChat(chat.id)}
                      >
                        Excluir
                      </button>
                    </div>
                  </li>
                ))
              ) : (
                <li className="text-xs text-[#666]">Nenhum chat</li>
              )}
            </ul>
          </section>

          <section className="mb-5">
            <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[#9b9b9b]">Projetos</h2>
            <ul className="space-y-1">
              {projects.length ? (
                projects.map((project) => (
                  <li
                    key={project.slug}
                    className={`flex items-center justify-between rounded-lg border px-2 py-2 text-xs ${
                      project.is_active ? "border-[#d97757]/50 bg-[#191919]" : "border-[#2e2e2e]"
                    }`}
                  >
                    <button type="button" className="flex-1 text-left font-medium" onClick={() => onSelectProject(project.slug)}>
                      {project.name}
                    </button>
                    <button
                      type="button"
                      className="ml-2 rounded border border-[#2e2e2e] px-2 py-0.5 text-[10px] hover:border-red-500/50"
                      onClick={() => onDeleteProject(project.slug)}
                    >
                      Excluir
                    </button>
                  </li>
                ))
              ) : (
                <li className="text-xs text-[#666]">Nenhum projeto</li>
              )}
            </ul>
            <button
              type="button"
              onClick={onNewProject}
              className="mt-2 min-h-9 w-full rounded-xl border border-[#2e2e2e] text-sm transition hover:border-[#d97757]/50 hover:bg-[#191919]"
            >
              Novo projeto
            </button>
          </section>

          <div className="mb-4">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-[#9b9b9b]">Ativo</p>
            <p className="mt-1 text-sm font-medium">{projectName}</p>
            {phase ? <p className="mt-1 text-xs text-[#9b9b9b]">Fase: {phase}</p> : null}
            {model ? <p className="mt-0.5 truncate font-mono text-[10px] text-[#9b9b9b]">{model}</p> : null}
          </div>

          <section className="mb-4">
            <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[#9b9b9b]">Tarefas</h2>
            <TaskTree tasks={tasks} />
          </section>

          <section>
            <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[#9b9b9b]">Alterações</h2>
            <ul className="max-h-32 overflow-auto font-mono text-[11px] text-[#9b9b9b]">
              {changes.length ? (
                changes.map((c, i) => (
                  <li key={i} className="border-b border-[#2e2e2e] py-1.5">
                    {c.path} <span className="text-[#666]">({c.action})</span>
                  </li>
                ))
              ) : (
                <li>—</li>
              )}
            </ul>
          </section>
        </div>

        {database ? <p className="text-[10px] text-[#d97757]/80">PostgreSQL</p> : null}
      </aside>
    </>
  );
}
