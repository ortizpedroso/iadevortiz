import type { TaskNode } from "../types";
import { TaskTree } from "./TaskTree";

type Props = {
  open: boolean;
  onToggle: () => void;
  projectName: string;
  tasks: TaskNode[];
  changes: { path: string; action: string }[];
  onNewProject: () => void;
  database: boolean;
};

export function Sidebar({
  open,
  onToggle,
  projectName,
  tasks,
  changes,
  onNewProject,
  database,
}: Props) {
  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-20 bg-black/50 md:hidden"
        hidden={!open}
        aria-label="Fechar menu"
        onClick={onToggle}
      />
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-72 flex-col gap-5 border-r border-slate-700 bg-[#0b1220] p-5 transition-transform md:static md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-emerald-500/15 text-emerald-400">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z" />
            </svg>
          </div>
          <div>
            <strong className="block text-sm">PKF</strong>
            <span className="text-xs text-slate-500">IA de desenvolvimento</span>
          </div>
        </div>

        <button
          type="button"
          onClick={onNewProject}
          className="min-h-11 rounded-lg border border-slate-600 text-sm font-medium transition hover:border-slate-500 hover:bg-slate-800"
        >
          Novo projeto
        </button>

        <section>
          <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Projeto atual</h2>
          <p className="text-sm">{projectName}</p>
        </section>

        <section>
          <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Tarefas</h2>
          <TaskTree tasks={tasks} />
        </section>

        <section className="min-h-0 flex-1">
          <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Alterações recentes</h2>
          <ul className="max-h-36 overflow-auto font-mono text-[11px] text-slate-500">
            {changes.length ? (
              changes.map((c, i) => (
                <li key={i} className="border-b border-slate-800 py-1">
                  {c.path} <span className="text-slate-600">({c.action})</span>
                </li>
              ))
            ) : (
              <li>—</li>
            )}
          </ul>
        </section>

        {database ? (
          <p className="text-[10px] text-emerald-500/80">PostgreSQL conectado</p>
        ) : null}
      </aside>
    </>
  );
}
