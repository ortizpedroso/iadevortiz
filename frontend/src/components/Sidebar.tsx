import type { TaskNode } from "../types";
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
      <aside className="fixed inset-y-0 left-14 z-30 flex w-72 flex-col gap-5 border-r border-[#2e2e2e] bg-[#212121] p-5 md:static md:z-0">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-[#9b9b9b]">Projeto</p>
          <p className="mt-1 text-sm font-medium">{projectName}</p>
          {phase ? <p className="mt-1 text-xs text-[#9b9b9b]">Fase: {phase}</p> : null}
          {model ? <p className="mt-0.5 truncate font-mono text-[10px] text-[#9b9b9b]">{model}</p> : null}
        </div>

        <button
          type="button"
          onClick={onNewProject}
          className="min-h-10 rounded-xl border border-[#2e2e2e] text-sm transition hover:border-[#d97757]/50 hover:bg-[#191919]"
        >
          Novo projeto
        </button>

        <section>
          <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[#9b9b9b]">Tarefas</h2>
          <TaskTree tasks={tasks} />
        </section>

        <section className="min-h-0 flex-1">
          <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[#9b9b9b]">Alterações</h2>
          <ul className="max-h-40 overflow-auto font-mono text-[11px] text-[#9b9b9b]">
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

        {database ? <p className="text-[10px] text-[#d97757]/80">PostgreSQL</p> : null}
      </aside>
    </>
  );
}
