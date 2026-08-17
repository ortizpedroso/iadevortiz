"""Grafo de build (piloto LangGraph-style) — atrás de PKF_USE_LANGGRAPH_BUILD=1.

Implementação nativa async (sem dependência langgraph) com os mesmos nós do /build clássico.
Substituir por LangGraph real requer aprovação para adicionar `langgraph` ao requirements.txt.
"""

from __future__ import annotations

from typing import Any, TypedDict

from pkf.tools.impl import verify_build as verify_build_tool
from pkf.workflow.compose import MAX_BUILD_RETRIES, run_brainstorm, verify_ok
from pkf.workflow.orchestrator import failed_agents, run_build_phases
from pkf.workflow.planner import group_tasks_into_phases, plan_build, plan_build_llm, plan_fix_tasks
from pkf.workflow.review import load_latest_review, parse_review_status
from pkf.workflow.tasks import TaskTracker
from pkf.workflow.compose import MAX_REVIEW_FIX_CYCLES
from pkf.workspace_index import begin_build_session


class BuildState(TypedDict, total=False):
    remainder: str
    tasks: list
    phases: list
    results: list
    verify: str
    attempt: int
    review_ok: bool
    review_reply: str
    error: str


async def node_plan(router, state: BuildState) -> BuildState:
    router.cycle.phase = "BUILD"
    if state.get("remainder"):
        router.cycle.set_spec(state["remainder"])
    router.cycle.persist(router.workspace.root)
    await run_brainstorm(router, router.cycle.active_spec)
    tasks = await plan_build_llm(
        router.client, router.model_to_use, router.workspace.root, router.cycle.active_spec
    )
    if not tasks:
        tasks = plan_build(router.workspace.root, router.cycle.active_spec)
    phases = group_tasks_into_phases(tasks)
    return {**state, "tasks": tasks, "phases": phases, "attempt": 0, "results": []}


async def node_build(router, state: BuildState, tracker: TaskTracker) -> BuildState:
    attempt = state.get("attempt", 0) + 1
    pending = failed_agents(state.get("results") or []) if attempt > 1 else None
    if attempt == 1:
        begin_build_session(router.workspace)
    results = await run_build_phases(
        router, state["phases"], tracker, only_agents=pending
    )
    verify = verify_build_tool(router.workspace)
    ok = verify_ok(verify) and not any(r[1].startswith("Erro:") for r in results)
    return {
        **state,
        "attempt": attempt,
        "results": results,
        "verify": verify,
        "build_ok": ok,
    }


async def node_review(router, state: BuildState, tracker: TaskTracker) -> BuildState:
    last_reply = ""
    for cycle in range(1, MAX_REVIEW_FIX_CYCLES + 1):
        last_reply = await router._auto_review()
        saved = load_latest_review(router.workspace.root, router.cycle.active_spec)
        review_text = saved or last_reply
        approved, issues = parse_review_status(review_text)
        if approved:
            return {**state, "review_ok": True, "review_reply": review_text or last_reply}
        if cycle >= MAX_REVIEW_FIX_CYCLES:
            break
        fix_tasks = plan_fix_tasks(router.cycle.active_spec, issues)
        fix_phases = group_tasks_into_phases(fix_tasks)
        await run_build_phases(router, fix_phases, tracker)
    return {**state, "review_ok": False, "review_reply": last_reply}


async def run_build_graph(router, remainder: str) -> str:
    """Executa pipeline /build como grafo de nós (piloto)."""
    state: BuildState = {"remainder": remainder}
    tracker = TaskTracker(router.workspace.root, db_context=router.db)

    state = await node_plan(router, state)
    tracker.reset_for_build(router.cycle.active_spec, [t.agent for t in state["tasks"]])
    await router.emit_task_tree(tracker)

    build_ok = False
    while state.get("attempt", 0) < MAX_BUILD_RETRIES:
        state = await node_build(router, state, tracker)
        build_ok = bool(state.get("build_ok"))
        if build_ok:
            break

    if not build_ok:
        verify = state.get("verify", "")
        lines = ["## Build (grafo) com erros", "", verify]
        for agent_name, reply in state.get("results") or []:
            lines.append(f"### {agent_name}\n{reply[:800]}")
        return "\n".join(lines)

    state = await node_review(router, state, tracker)
    if state.get("review_ok"):
        return (
            "Build via grafo concluído e review aprovado."
            if not router.ui_mode
            else "Pronto! Build (grafo piloto) concluído e aprovado no review."
        )
    return (
        "Build via grafo concluído, mas review ainda reprovado após correções."
        if router.ui_mode
        else state.get("review_reply") or "Review reprovado."
    )
