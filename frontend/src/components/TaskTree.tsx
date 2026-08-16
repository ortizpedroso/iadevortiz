import type { TaskNode } from "../types";

function icon(status?: string) {
  if (status === "done") return "✓";
  if (status === "running") return "…";
  if (status === "failed") return "✗";
  return "○";
}

function TaskItem({ node }: { node: TaskNode }) {
  const cls =
    node.status === "done"
      ? "text-emerald-400"
      : node.status === "running"
        ? "text-[#d97757]"
        : node.status === "failed"
          ? "text-red-400"
          : "text-[#666]";
  return (
    <li className={`border-l-2 border-[#2e2e2e] pl-2 ${cls}`}>
      {icon(node.status)} {node.title}
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
  if (!tasks.length) return <p className="text-sm text-[#666]">—</p>;
  return (
    <ul className="space-y-1 text-sm">
      {tasks.map((t) => (
        <TaskItem key={t.id} node={t} />
      ))}
    </ul>
  );
}
