from __future__ import annotations

import asyncio

from pkf.workflow.planner import BuildTask


async def run_build_tasks(router, tasks: list[BuildTask]) -> list[tuple[str, str]]:
    async def _run(task: BuildTask) -> tuple[str, str]:
        agent = router.agents.get(task.agent)
        if not agent:
            return task.agent, f"Agente '{task.agent}' indisponível."
        await router.emit("parallel_start", agent=task.agent, node=task.node_id)
        try:
            reply = await agent.process(task.instruction)
            await router.emit("parallel_done", agent=task.agent, node=task.node_id)
            return task.agent, reply or "(sem resposta)"
        except Exception as exc:
            await router.emit("parallel_error", agent=task.agent, error=str(exc))
            return task.agent, f"Erro: {exc}"

    if not tasks:
        return []
    results = await asyncio.gather(*[_run(t) for t in tasks])
    return list(results)
