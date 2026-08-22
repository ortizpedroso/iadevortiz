from __future__ import annotations

import asyncio

from openai import APIConnectionError, APIStatusError, APITimeoutError

from pkf.workflow.handoff import handoff_context_for_deps, load_handoffs, save_handoff
from pkf.workflow.planner import BuildTask
from pkf.workflow.task_graph import ready_tasks
from pkf.workflow.tasks import TaskTracker

_TASK_LABELS = {
    "frontend": "Criando interface",
    "backend": "Criando backend",
    "logic": "Implementando regras",
    "tester": "Escrevendo testes",
}


async def run_build_tasks(
    router,
    tasks: list[BuildTask],
    tracker: TaskTracker,
    *,
    only_agents: set[str] | None = None,
) -> list[tuple[str, str]]:
    return await run_build_dag(router, tasks, tracker, only_agents=only_agents)


async def run_build_phases(
    router,
    phases: list[list[BuildTask]],
    tracker: TaskTracker,
    *,
    only_agents: set[str] | None = None,
) -> list[tuple[str, str]]:
    """Compatibilidade: achata fases e executa como DAG."""
    flat = [t for phase in phases for t in phase]
    return await run_build_dag(router, flat, tracker, only_agents=only_agents)


async def run_build_dag(
    router,
    tasks: list[BuildTask],
    tracker: TaskTracker,
    *,
    only_agents: set[str] | None = None,
    initial_completed: set[str] | None = None,
) -> list[tuple[str, str]]:
    """Executa DAG com ordenação topológica dinâmica (grau de entrada zero em paralelo)."""
    if not tasks:
        return []

    pending = {t.task_id: t for t in tasks}
    completed: set[str] = set(initial_completed or ())
    skipped: set[str] = set()
    results: list[tuple[str, str]] = []
    total = len(tasks)
    step = 0

    async def _run(task: BuildTask) -> tuple[str, str]:
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
        handoff_block = handoff_context_for_deps(router.workspace.root, task.depends_on)
        payload = task.instruction + handoff_block if handoff_block else task.instruction
        try:
            reply = await agent.process(payload)
            summary = (reply or "(sem resposta)")[:2000]
            save_handoff(
                router.workspace.root,
                task.task_id,
                agent=task.agent,
                summary=summary,
            )
            if router.db and hasattr(router.db, "save_handoffs"):
                store = load_handoffs(router.workspace.root)
                await router.db.save_handoffs(store)
            tracker.set_child_status(task.agent, "done")
            await router.emit("parallel_done", agent=task.agent, node=task.node_id)
            await router.emit_task_tree(tracker)
            await _notify_agent_done(router, task)
            return task.agent, reply or "(sem resposta)"
        except (APIConnectionError, APIStatusError, APITimeoutError, RuntimeError, ValueError) as exc:
            tracker.set_child_status(task.agent, "failed")
            await router.emit("parallel_error", agent=task.agent, error=str(exc))
            await router.emit_task_tree(tracker)
            return task.agent, f"Erro: {exc}"

    while pending:
        batch = ready_tasks(list(pending.values()), completed)
        if only_agents is not None:
            defer: list[BuildTask] = []
            runnable: list[BuildTask] = []
            for task in batch:
                if task.agent in only_agents:
                    runnable.append(task)
                else:
                    defer.append(task)
            for task in defer:
                pending.pop(task.task_id, None)
                completed.add(task.task_id)
            batch = runnable
        if not batch:
            blocked = [t for t in pending.values() if t.task_id not in skipped]
            if not blocked:
                break
            for task in blocked:
                if only_agents is not None and task.agent not in only_agents:
                    skipped.add(task.task_id)
                    pending.pop(task.task_id, None)
                    completed.add(task.task_id)
                else:
                    raise RuntimeError(
                        f"Deadlock no DAG: dependências não satisfeitas para {task.task_id}"
                    )
            continue

        layer_agents = {t.agent for t in batch}
        await router.emit(
            "build_phase",
            phase=len(completed),
            label=f"DAG — {', '.join(sorted(layer_agents))}",
        )
        if router.ui_mode:
            await router._emit_progress(f"Executando: {', '.join(sorted(layer_agents))}…")

        if len(batch) == 1:
            task = batch[0]
            pending.pop(task.task_id, None)
            result = await _run(task)
            results.append(result)
            completed.add(task.task_id)
        else:
            coros = []
            batch_tasks: list[BuildTask] = []
            for task in batch:
                pending.pop(task.task_id, None)
                batch_tasks.append(task)
            coros = [_run(t) for t in batch_tasks]
            batch_results = await asyncio.gather(*coros)
            results.extend(batch_results)
            for task in batch_tasks:
                completed.add(task.task_id)

    return results


async def _notify_agent_done(router, task: BuildTask) -> None:
    from pkf.web.state_events import emit_state_event

    session_id = None
    if router.db and getattr(router.db, "session_id", None):
        session_id = str(router.db.session_id)
    await emit_state_event(
        {
            "kind": "agent_phase_done",
            "task_id": task.task_id,
            "agent": task.agent,
            "session_id": session_id,
        }
    )


def failed_agents(results: list[tuple[str, str]]) -> set[str]:
    return {name for name, reply in results if reply.startswith("Erro:")}
