from __future__ import annotations

import asyncio

from pkf.workflow.planner import BuildTask
from pkf.workflow.tasks import TaskTracker

_TASK_LABELS = {
    "frontend": "Criando interface",
    "backend": "Criando backend",
    "logic": "Implementando regras",
    "tester": "Escrevendo testes",
}


async def run_build_tasks(router, tasks: list[BuildTask], tracker: TaskTracker) -> list[tuple[str, str]]:
    total = len(tasks)

    async def _run(index: int, task: BuildTask) -> tuple[str, str]:
        label = _TASK_LABELS.get(task.agent, "Implementando")
        tracker.set_child_status(task.agent, "running")
        await router.emit(
            "task_progress",
            step=index + 1,
            total=total,
            message=f"Passo {index + 1}/{total}: {label}…",
        )
        await router.emit_task_tree(tracker)
        agent = router.agents.get(task.agent)
        if not agent:
            tracker.set_child_status(task.agent, "failed")
            return task.agent, f"Agente '{task.agent}' indisponível."
        await router.emit("parallel_start", agent=task.agent, node=task.node_id)
        try:
            reply = await agent.process(task.instruction)
            tracker.set_child_status(task.agent, "done")
            await router.emit("parallel_done", agent=task.agent, node=task.node_id)
            await router.emit_task_tree(tracker)
            return task.agent, reply or "(sem resposta)"
        except Exception as exc:
            tracker.set_child_status(task.agent, "failed")
            await router.emit("parallel_error", agent=task.agent, error=str(exc))
            await router.emit_task_tree(tracker)
            return task.agent, f"Erro: {exc}"

    if not tasks:
        return []
    results = await asyncio.gather(*[_run(i, t) for i, t in enumerate(tasks)])
    return list(results)
