import type { TaskNode } from "../types";

function icon(status?: string) {
  if (status === "done") return "✓";
  if (status === "running") return "…";
  if (status === "failed") return "✗";
  if (status === "skipped") return "⊘";
  if (status === "handoff") return "↪";
  return "○";
}

function TaskItem({ node }: { node: TaskNode }) {
  const cls =
    node.status === "done"
      ? "text-emerald-400"
      : node.status === "running"
        ? "text-[var(--pkf-accent)]"
        : node.status === "failed"
          ? "text-red-400"
          : node.status === "skipped"
            ? "text-amber-500/80"
            : node.status === "handoff"
              ? "text-sky-400"
              : "text-[var(--pkf-text-dim)]";
  return (
    <li className={`border-l-2 border-[var(--pkf-border)] pl-2 ${cls}`}>
      {icon(node.status)} {node.title}
      {node.detail ? (
        <span className="block text-xs text-[var(--pkf-text-dim)] mt-0.5 ml-4">{node.detail}</span>
      ) : null}
      {node.children?.length ? (
        <ul className="mt-1 ml-3 space-y-1">
          {node.children.map((c) => (
            <TaskItem key={c.id} node={c} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export function TaskTree({ tasks }: { tasks: TaskNode[] }) {
  if (!tasks.length) return <p className="text-sm text-[var(--pkf-text-dim)]">—</p>;
  return (
    <ul className="space-y-1 text-sm">
      {tasks.map((t) => (
        <TaskItem key={t.id} node={t} />
      ))}
    </ul>
  );
}
