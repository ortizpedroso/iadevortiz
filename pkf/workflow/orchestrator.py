from __future__ import annotations

import asyncio

from openai import APIConnectionError, APIStatusError, APITimeoutError

from pkf.workflow.planner import BuildTask
from pkf.workflow.tasks import TaskTracker

_TASK_LABELS = {
    "frontend": "Criando interface",
    "backend": "Criando backend",
    "logic": "Implementando regras",
    "tester": "Escrevendo testes",
}

_PHASE_LABELS = {
    0: "Fase 1 — backend/serviços",
    1: "Fase 2 — regras de negócio",
    2: "Fase 3 — interface",
    3: "Fase 4 — testes",
}


async def run_build_tasks(
    router,
    tasks: list[BuildTask],
    tracker: TaskTracker,
    *,
    only_agents: set[str] | None = None,
) -> list[tuple[str, str]]:
    phases = [[t] for t in tasks]
    return await run_build_phases(router, phases, tracker, only_agents=only_agents)


async def run_build_phases(
    router,
    phases: list[list[BuildTask]],
    tracker: TaskTracker,
    *,
    only_agents: set[str] | None = None,
) -> list[tuple[str, str]]:
    """Executa fases em sequência; tarefas dentro da mesma fase em paralelo."""
    results: list[tuple[str, str]] = []
    total = sum(len(p) for p in phases)
    step = 0

    for phase_index, phase_tasks in enumerate(phases):
        runnable = [t for t in phase_tasks if not only_agents or t.agent in only_agents]
        if not runnable:
            continue
        phase_label = _PHASE_LABELS.get(phase_index, f"Fase {phase_index + 1}")
        await router.emit("build_phase", phase=phase_index, label=phase_label)
        if router.ui_mode:
            await router._emit_progress(phase_label + "…")

        async def _run(task: BuildTask, index: int) -> tuple[str, str]:
            nonlocal step
            step += 1
            label = _TASK_LABELS.get(task.agent, "Implementando")
            tracker.set_child_status(task.agent, "running")
            await router.emit(
                "task_progress",
                step=step,
                total=total,
                message=f"Passo {step}/{total}: {label}…",
                agent=task.agent,
                provider=router.provider_name,
            )
            await router.emit(
                "active_agent",
                agent=task.agent,
                provider=router.provider_name,
                model=router.agents.get(task.agent).model if router.agents.get(task.agent) else router.model_to_use,
            )
            await router.emit_task_tree(tracker)
            agent = router.agents.get(task.agent)
            if not agent:
                tracker.set_child_status(task.agent, "failed")
                return task.agent, f"Agente '{task.agent}' indisponível."
            router.bind_agent_provider(task.agent)
            await router.emit("parallel_start", agent=task.agent, node=task.node_id)
            try:
                reply = await agent.process(task.instruction)
                tracker.set_child_status(task.agent, "done")
                await router.emit("parallel_done", agent=task.agent, node=task.node_id)
                await router.emit_task_tree(tracker)
                return task.agent, reply or "(sem resposta)"
            except (APIConnectionError, APIStatusError, APITimeoutError, RuntimeError, ValueError) as exc:
                tracker.set_child_status(task.agent, "failed")
                await router.emit("parallel_error", agent=task.agent, error=str(exc))
                await router.emit_task_tree(tracker)
                return task.agent, f"Erro: {exc}"

        if len(runnable) == 1:
            results.append(await _run(runnable[0], step))
        else:
            batch = await asyncio.gather(*[_run(t, i) for i, t in enumerate(runnable)])
            results.extend(batch)

    return results


def failed_agents(results: list[tuple[str, str]]) -> set[str]:
    return {name for name, reply in results if reply.startswith("Erro:")}
