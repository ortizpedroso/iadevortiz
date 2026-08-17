from __future__ import annotations

from pathlib import Path

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from pkf.agents.base import Agent
from pkf.agents.developer import DeveloperAgent
from pkf.agents.prompts import AGENT_PROMPTS, DEVELOPER_AGENTS
from pkf.classifier import Intent, classify_intent, classify_intent_llm
from pkf.config import RELEVANCE_THRESHOLD, agent_provider_override, model_for_task, rate_limit_cooldown_seconds
from pkf.graph.project import ProjectGraph
from pkf.judge import evaluate_build_goal
from pkf.memory.persistent import append_memory_note, read_memory_context, write_checkpoint
from pkf.memory.store import MemoryStore, export_graph
from pkf.provider_errors import should_rotate_provider
from pkf.provider_pool import ProviderPool
from pkf.spec.store import active_spec_preview, approve_spec, load_spec, update_spec_stack
from pkf.skills.loader import load_skills_for_project
from pkf.spec.updater import append_build_changelog, save_platform_spec
from pkf.tools.impl import verify_build as verify_build_tool
from pkf.workspace_index import begin_build_session
from pkf.tools.registry import ToolRegistry, tools_for_agent
from pkf.workflow.compose import MAX_BUILD_RETRIES, MAX_REVIEW_FIX_CYCLES, run_brainstorm, verify_ok
from pkf.workflow.cycle import DevCycle, parse_command
from pkf.workflow.orchestrator import failed_agents, run_build_phases
from pkf.workflow.planner import group_tasks_into_phases, plan_build, plan_build_llm, plan_fix_tasks
from pkf.workflow.review import load_latest_review, parse_review_status
from pkf.workflow.tasks import TaskTracker
from pkf.projects.manager import slug_from_request
from pkf.web.preview import preview_info
from pkf.workspace import Workspace


class Router:
    def __init__(
        self,
        provider_name: str,
        workspace: Workspace,
        fallback_provider: str | None = None,
        client: AsyncOpenAI | None = None,
        model: str | None = None,
        supports_tools: bool = True,
        ui_mode: bool = False,
        provider_pool: ProviderPool | None = None,
    ):
        self.workspace = workspace
        self.ui_mode = ui_mode
        self.pool = provider_pool or ProviderPool.create(start=provider_name)
        self.fallback_provider = fallback_provider
        if client is None:
            client, config = self.pool.get_client()
            model = config.model
            supports_tools = config.supports_tools
        self.client = client
        self.provider_name = self.pool.current_name
        self.model_to_use = model or "llama3:8b"
        self.supports_tools = supports_tools
        self.memory = MemoryStore(workspace.root)
        self.cycle = DevCycle.load(workspace.root)
        self.agents: dict[str, Agent] = {}
        self._event_handler = None
        self._last_user_query = ""
        self._active_agent: str | None = None
        self.db = None
        self._register_core_agents()
        self._restore_memory_agents()
        save_platform_spec(workspace.root)

    def set_event_handler(self, handler) -> None:
        self._event_handler = handler

    async def emit(self, event_type: str, **payload) -> None:
        if self.ui_mode and event_type in {
            "plan",
            "parallel_start",
            "parallel_done",
            "parallel_error",
            "build_verify",
            "routing",
            "tool",
            "thinking",
        }:
            return
        if event_type == "task_progress" and self.ui_mode:
            msg = payload.get("message", "Trabalhando…")
            agent = payload.get("agent")
            provider = payload.get("provider")
            if agent:
                msg = f"{msg} ({agent} · {provider or self.provider_name})"
            await self._emit_progress(msg)
            if self._event_handler:
                await self._event_handler(
                    {
                        "type": "active_agent",
                        "agent": agent,
                        "provider": provider or self.provider_name,
                        "model": payload.get("model") or self.model_to_use,
                    }
                )
            return
        if self._event_handler:
            await self._event_handler({"type": event_type, **payload})

    async def _emit_progress(self, message: str) -> None:
        if self._event_handler:
            await self._event_handler({"type": "progress", "message": message})

    async def emit_task_tree(self, tracker: TaskTracker) -> None:
        if self._event_handler:
            await self._event_handler({"type": "task_tree", "tasks": tracker.to_list()})

    def snapshot(self) -> dict:
        preview = active_spec_preview(self.workspace.root, self.cycle.active_spec)
        graph = ProjectGraph(self.workspace.root)
        project_preview = preview_info(self.workspace)
        if project_preview.get("entry"):
            project_preview["path"] = f"/preview/{project_preview['entry']}"
        tasks = TaskTracker(self.workspace.root, db_context=self.db).to_list()
        return {
            "provider": self.provider_name,
            "provider_pool": self.pool.names,
            "provider_router": self.pool.status(),
            "model": self.model_to_use,
            "workspace": str(self.workspace.root),
            "project": self.workspace.project,
            "project_name": self.workspace.project_label,
            "phase": self.cycle.phase,
            "active_spec": self.cycle.active_spec,
            "spec_status": self.cycle.spec_status,
            "spec_preview": preview,
            "project_preview": project_preview,
            "project_graph": graph.to_dict() if not self.ui_mode else None,
            "last_agent": self.cycle.last_agent or self._active_agent or "pkf",
            "active_agent": self._active_agent,
            "agents": list(AGENT_PROMPTS),
            "goal": self.cycle.goal,
            "tasks": tasks,
            "database": bool(self.db and self.db.enabled),
        }

    def _ensure_project(self, text: str) -> None:
        if self.workspace.project:
            return
        slug = slug_from_request(text)
        self.workspace.set_project(slug)
        self._register_core_agents()
        self.cycle = DevCycle.load(self.workspace.root)

    def _user_reply(self, message: str) -> str:
        if "Limite de ferramentas atingido" in message:
            return (
                "Implementei parte do projeto, mas ainda não terminei tudo.\n\n"
                "Use **Ver projeto** para ver o que já foi criado e me diga o que quer ajustar ou completar."
            )
        return message

    async def try_rotate_provider(self, exc: Exception) -> bool:
        if not should_rotate_provider(self.pool.current_name, exc):
            return False
        cooldown = rate_limit_cooldown_seconds(exc)
        if isinstance(exc, APIStatusError) and exc.status_code in {401, 403}:
            cooldown = max(cooldown, 120)
        if not self.pool.rotate(str(exc), cooldown_seconds=cooldown):
            return False
        client, config = self.pool.get_client()
        self.client = client
        self.provider_name = self.pool.current_name
        self.model_to_use = config.model
        self.supports_tools = config.supports_tools
        self._register_core_agents()
        if self.ui_mode:
            await self._emit_progress("Continuando com outro provedor…")
        return True

    def reset_conversation(self) -> None:
        for agent in self.agents.values():
            if agent.messages:
                agent.messages = [agent.messages[0]]
        self.workspace.clear_project()
        self.cycle = DevCycle()
        self.cycle.persist(self.workspace.root)
        self._register_core_agents()

    def bind_agent_provider(self, agent_name: str) -> None:
        """Aplica override de provider/modelo por agente antes de process()."""
        agent = self.agents.get(agent_name)
        if not agent:
            return
        override = agent_provider_override(agent_name)
        if override:
            client, config = self.pool.get_client(override)
            agent.client = client
            agent.model = model_for_task(agent_name, config.model)
        else:
            client, config = self.pool.get_client()
            agent.client = client
            agent.model = model_for_task(agent_name, config.model)
        self._active_agent = agent_name

    def _register_core_agents(self) -> None:
        context = self.workspace.scan_summary()
        memory_ctx = read_memory_context(self.workspace.root)
        query = self._last_user_query or self.workspace.project or ""
        skills = load_skills_for_project(self.workspace.project, query)
        for name, prompt in AGENT_PROMPTS.items():
            system_prompt = f"{prompt}\n\nContexto do projeto:\n{context}"
            if memory_ctx:
                system_prompt += f"\n\n{memory_ctx}"
            if skills:
                system_prompt += f"\n\nSkills e templates relevantes:\n{skills}"
            core, optional = tools_for_agent(name)
            tools = ToolRegistry(self.workspace, core, optional, router=self)
            cls = DeveloperAgent if name in DEVELOPER_AGENTS else Agent
            agent_model = model_for_task(name, self.model_to_use)
            self.agents[name] = cls(
                name=name,
                client=self.client,
                model=agent_model,
                system_prompt=system_prompt,
                router=self,
                tools=tools,
                supports_tools=self.supports_tools,
            )

    def restore_chat_history(self, messages: list[dict], limit: int = 24) -> None:
        """Reidrata mensagens recentes nos agentes após troca de chat."""
        recent = [
            {"role": m.get("role"), "content": m.get("content", "")}
            for m in messages[-limit:]
            if m.get("role") in ("user", "assistant") and (m.get("content") or "").strip()
        ]
        if not recent:
            return
        for agent in self.agents.values():
            system = agent.messages[0] if agent.messages else None
            agent.messages = [system] if system else []
            agent.messages.extend(recent)

    def _restore_memory_agents(self) -> None:
        for name, summary in self.memory.index.items():
            if name in self.agents:
                continue
            self.agents[name] = Agent(
                name=name,
                client=self.client,
                model=self.model_to_use,
                system_prompt=f"Você é um agente de memória da PKF. Responda só com base neste resumo:\n{summary}",
                router=self,
                tools=None,
                supports_tools=False,
            )

    def register_agent(self, agent: Agent, summary: str) -> None:
        if agent.name in self.agents:
            print(f"[Roteador] Agente '{agent.name}' já existe; atualizando o índice de memória.")
        self.agents[agent.name] = agent
        self.memory.register(agent.name, summary)
        print(f"[Roteador] Agente de memória '{agent.name}' registrado.")

    def _find_memory_agent(self, user_input: str) -> Agent | None:
        name, score = self.memory.find(user_input, RELEVANCE_THRESHOLD)
        if name and name in self.agents:
            print(f"[Roteador] Memória relevante ({score} termos) → {name}")
            return self.agents[name]
        return None

    async def _classify(self, user_input: str) -> Intent:
        last = self.cycle.last_agent
        intent = classify_intent(user_input, last)
        if intent.source == "fallback":
            intent = await classify_intent_llm(self.client, self.model_to_use, user_input, last)
        return intent

    async def handle(self, user_input: str) -> str | None:
        self._last_user_query = user_input
        command, remainder = parse_command(user_input)
        if command == "/help":
            await self.emit("routing", agent="sistema", kind="command", source="command")
            return help_text()
        if command == "/status":
            await self.emit("routing", agent="sistema", kind="command", source="command")
            return self.cycle.status_text()
        if command == "/agents":
            await self.emit("routing", agent="sistema", kind="command", source="command")
            return "Agentes: " + ", ".join(sorted(self.agents))
        if command == "/workspace":
            await self.emit("routing", agent="sistema", kind="command", source="command")
            return self.workspace.scan_summary()
        if command == "/graph":
            dest = Path(self.workspace.root) / "knowledge_graph.png"
            agent_name = self.cycle.last_agent or "architect"
            agent = self.agents.get(agent_name)
            if not agent:
                return "Nenhum agente ativo para exportar o grafo."
            return export_graph(agent.graph, dest)
        if command == "/goal":
            self.cycle.goal = remainder.strip() or self.cycle.goal
            self.cycle.persist(self.workspace.root)
            await self.emit("routing", agent="sistema", kind="command", source="command")
            if not self.cycle.goal:
                return "Informe a meta: /goal o preview deve mostrar index.html funcional"
            return f"Meta registrada: {self.cycle.goal}"

        memory_agent = None if command else self._find_memory_agent(user_input)
        if memory_agent and not command:
            self.cycle.last_agent = memory_agent.name
            self.cycle.persist(self.workspace.root)
            await self.emit("routing", agent=memory_agent.name, kind="memory", source="memory")
            return await memory_agent.process(user_input)

        if command == "/build":
            self.cycle = DevCycle.load(self.workspace.root)
            if self.cycle.active_spec:
                preview = active_spec_preview(self.workspace.root, self.cycle.active_spec)
                if preview and preview.get("status") != "approved":
                    await self.emit("spec_preview", spec=preview)
                    if self.ui_mode:
                        return (
                            "A spec precisa ser aprovada antes do /build. "
                            "Revise o painel de especificação e clique em Aprovar."
                        )
                    return (
                        "A spec precisa ser aprovada antes do /build. "
                        "Revise o painel à direita, ajuste a stack se quiser e clique em Aprovar."
                    )
            return await self._run_parallel_build(remainder)

        intent = await self._classify(user_input)
        if intent.kind in {"feature", "change"} or command == "/spec":
            self._ensure_project(user_input)
        agent = self.agents.get(intent.agent) or self.agents["generalista"]
        payload = user_input
        if agent.name in DEVELOPER_AGENTS:
            _, payload = self.cycle.apply(command, intent.kind, remainder or user_input)
            if command == "/spec" and remainder:
                self.cycle.set_spec(remainder.splitlines()[0][:60])
            if intent.kind == "review_request" and not command:
                _, payload = self.cycle.apply("/review", intent.kind, user_input)
            if intent.kind == "test_request" and agent.name != "tester":
                agent = self.agents["tester"]
                payload = user_input

        print(f"[Roteador] {intent.source} → {agent.name} ({intent.kind})")
        await self.emit("routing", agent=agent.name, kind=intent.kind, source=intent.source)
        self.cycle.last_agent = agent.name
        self.cycle.persist(self.workspace.root)
        self.bind_agent_provider(agent.name)
        reply = await agent.process(payload)
        self.cycle = DevCycle.load(self.workspace.root)
        preview = active_spec_preview(self.workspace.root, self.cycle.active_spec)
        if preview and preview.get("status") == "pending_approval":
            if self.ui_mode:
                await self.emit("spec_preview", spec=preview)
                return self._user_reply(reply) if reply else reply
            await self.emit("spec_preview", spec=preview)
        return self._user_reply(reply) if self.ui_mode and reply else reply

    async def _auto_approve_spec(self) -> None:
        name = self.cycle.active_spec
        if not name:
            return
        preview = active_spec_preview(self.workspace.root, name)
        if not preview or preview.get("status") == "approved":
            return
        confirmed = preview.get("suggested_stack") or {}
        approve_spec(self.workspace.root, name, confirmed)
        self.cycle = DevCycle.load(self.workspace.root)
        self.cycle.spec_status = "approved"
        self.cycle.persist(self.workspace.root)

    async def _run_parallel_build(self, remainder: str) -> str:
        self.cycle.phase = "BUILD"
        if remainder:
            self.cycle.set_spec(remainder)
        self.cycle.persist(self.workspace.root)
        write_checkpoint(
            self.workspace.root,
            "BUILD",
            self.cycle.active_spec,
            "Iniciando pipeline em fases",
        )

        if self.ui_mode:
            await self._emit_progress("Analisando contexto do projeto…")
        brainstorm = await run_brainstorm(self, self.cycle.active_spec)
        if brainstorm:
            write_checkpoint(
                self.workspace.root,
                "BUILD",
                self.cycle.active_spec,
                brainstorm[:2000],
            )

        tasks = await plan_build_llm(self.client, self.model_to_use, self.workspace.root, self.cycle.active_spec)
        if not tasks:
            tasks = plan_build(self.workspace.root, self.cycle.active_spec)
        phases = group_tasks_into_phases(tasks)

        tracker = TaskTracker(self.workspace.root, db_context=self.db)
        tracker.reset_for_build(self.cycle.active_spec, [t.agent for t in tasks])
        await self.emit_task_tree(tracker)
        await self.emit(
            "plan",
            tasks=[{"agent": t.agent, "node": t.node_id, "phase": t.phase} for t in tasks],
        )

        begin_build_session(self.workspace)
        if self.ui_mode:
            await self._emit_progress("Implementando em fases (backend → lógica → frontend)…")

        results: list[tuple[str, str]] = []
        verify = ""
        attempt = 0
        pending_agents: set[str] | None = None
        while attempt < MAX_BUILD_RETRIES:
            attempt += 1
            if attempt > 1:
                tracker.set_phase_status("T2", "running")
                await self._emit_progress(
                    f"Reexecutando agentes com falha (tentativa {attempt}/{MAX_BUILD_RETRIES})…"
                )
            results = await run_build_phases(
                self,
                phases,
                tracker,
                only_agents=pending_agents,
            )
            errors = [reply for _, reply in results if reply.startswith("Erro:")]
            verify = verify_build_tool(self.workspace)
            await self.emit("build_verify", result=verify)
            ok = verify_ok(verify) and not errors
            tracker.set_phase_status("T3", "done" if ok else "failed")
            if ok:
                tracker.set_phase_status("T2", "done")
            await self.emit_task_tree(tracker)
            if ok:
                break
            pending_agents = failed_agents(results) or {t.agent for t in tasks}

        errors = [reply for _, reply in results if reply.startswith("Erro:")]
        if errors or not verify_ok(verify):
            if self.ui_mode:
                return (
                    "Encontrei dificuldades ao implementar parte do projeto. "
                    "Descreva o que deseja ajustar e tento de novo."
                )
            lines = ["## Build em fases com erros", "", verify, ""]
            for agent_name, reply in results:
                lines.append(f"### {agent_name}")
                lines.append(reply[:1500])
                lines.append("")
            lines.append("Review automático omitido devido a erros nos agentes.")
            return "\n".join(lines)

        append_build_changelog(self.workspace.root, self.cycle.active_spec)

        spec_body = ""
        if self.cycle.active_spec:
            doc = load_spec(self.workspace.root, self.cycle.active_spec)
            if doc:
                spec_body = doc.body

        approved, judge_note = await evaluate_build_goal(
            self.provider_name,
            spec_body,
            verify,
            self.cycle.goal,
        )

        tracker.set_phase_status("T4", "running")
        review_ok, review_reply = await self._run_review_fix_loop(tracker)
        tracker.set_phase_status("T4", "done" if review_ok else "failed")
        tracker.set_phase_status("T5", "done" if review_ok and approved else "failed")
        await self.emit_task_tree(tracker)
        write_checkpoint(
            self.workspace.root,
            "REVIEW",
            self.cycle.active_spec,
            review_reply[:2000] if review_reply else judge_note,
        )
        append_memory_note(
            self.workspace.root,
            "Build",
            f"Spec: {self.cycle.active_spec}\nVerificação: {verify[:400]}\nJuiz: {judge_note}\nReview OK: {review_ok}",
        )

        if self.ui_mode:
            info = preview_info(self.workspace)
            if not review_ok:
                return (
                    "Implementei o projeto, mas o review ainda aponta pendências após correções automáticas.\n\n"
                    "Use **Ver projeto** e descreva o que ajustar, ou rode `/review` manualmente."
                )
            if not approved:
                return (
                    "Implementação revisada e aprovada pelo revisor, mas a meta (/goal) ainda não foi totalmente atingida.\n\n"
                    f"{judge_note}\n\nUse **Ver projeto** e diga o que ajustar."
                )
            if info.get("available"):
                return (
                    "Pronto! Projeto implementado em fases, verificado e aprovado no review.\n\n"
                    "Use **Ver projeto** no topo para abrir o preview."
                )
            return (
                "Implementação concluída e aprovada no review. Assim que houver index.html, "
                "o link **Ver projeto** aparecerá no topo."
            )

        lines = ["## Build em fases concluído", "", verify, ""]
        for agent_name, reply in results:
            lines.append(f"### {agent_name}")
            lines.append(reply[:1500])
            lines.append("")

        lines.append("## Juiz (/goal)")
        lines.append(judge_note)
        lines.append("## Review (loop até aprovação)")
        lines.append(review_reply or "")
        lines.append(f"\nReview aprovado: {'sim' if review_ok else 'não'}")
        return "\n".join(lines)

    async def _run_review_fix_loop(self, tracker: TaskTracker) -> tuple[bool, str]:
        """Review → fix → review até aprovação ou esgotar ciclos."""
        last_reply = ""
        for cycle in range(1, MAX_REVIEW_FIX_CYCLES + 1):
            if self.ui_mode:
                await self._emit_progress(f"Review automático ({cycle}/{MAX_REVIEW_FIX_CYCLES})…")
            last_reply = await self._auto_review()
            saved = load_latest_review(self.workspace.root, self.cycle.active_spec)
            review_text = saved or last_reply
            approved, issues = parse_review_status(review_text)
            if approved:
                return True, review_text or last_reply
            if cycle >= MAX_REVIEW_FIX_CYCLES:
                break
            if self.ui_mode:
                await self._emit_progress(
                    f"Corrigindo {len(issues)} problema(s) apontados no review…"
                )
            fix_tasks = plan_fix_tasks(self.cycle.active_spec, issues)
            fix_phases = group_tasks_into_phases(fix_tasks)
            await run_build_phases(self, fix_phases, tracker)
            verify = verify_build_tool(self.workspace)
            if not verify_ok(verify):
                last_reply += "\n\nVerificação pós-correção falhou."

        return False, last_reply

    async def _auto_review(self) -> str:
        self.cycle.phase = "REVIEW"
        self.cycle.last_agent = "reviewer"
        self.cycle.persist(self.workspace.root)
        self.bind_agent_provider("reviewer")
        await self.emit("routing", agent="reviewer", kind="command", source="auto")
        _, review_payload = self.cycle.apply("/review", "command", "")
        return await self.agents["reviewer"].process(review_payload) or ""

    async def start_session(self) -> None:
        try:
            print("--- PKF · IA de Desenvolvimento ---")
            print(f"Workspace: {self.workspace.root}")
            print("Digite /help para comandos. 'sair' encerra.")
            print("-" * 40)
            while True:
                user_input = await _read_input("Você: ")
                if user_input.lower() in {"sair", "exit", "quit"}:
                    print("--- Sessão encerrada ---")
                    break
                if not user_input.strip():
                    continue
                response = await self.handle(user_input)
                if response:
                    print(f"\nPKF ({self.cycle.last_agent or 'sistema'}):\n{response}\n")
            self._export_last_graph()
        except APIStatusError as exc:
            print(f"\n--- Erro de API com '{self.provider_name}' ({exc.status_code}) ---")
            if exc.status_code == 429 and self.fallback_provider:
                print(f"--- Fallback para '{self.fallback_provider}' ---")
                fallback = Router(self.fallback_provider, self.workspace)
                await fallback.start_session()
            else:
                print(exc)
        except (APIConnectionError, APITimeoutError):
            print(f"\n--- Falha de conexão com '{self.provider_name}' ---")
            if self.fallback_provider and self.fallback_provider != self.provider_name:
                print(f"--- Tentando '{self.fallback_provider}' ---")
                fallback = Router(self.fallback_provider, self.workspace)
                await fallback.start_session()
        except ValueError as exc:
            print(f"\n--- Erro de configuração ---: {exc}")

    def _export_last_graph(self) -> None:
        agent_name = self.cycle.last_agent
        agent = self.agents.get(agent_name) if agent_name else None
        if agent and agent.graph.number_of_nodes() > 0:
            dest = self.workspace.root / "knowledge_graph.png"
            print(export_graph(agent.graph, dest))


async def _read_input(prompt: str) -> str:
    import asyncio

    return await asyncio.to_thread(input, prompt)


def help_text() -> str:
    return """
Comandos:
  /spec [nome]     Abre ou continua a especificação
  /build [nome]    Implementa a spec (fases + review→fix loop)
  /review          Revisa o código contra a spec
  /goal [meta]     Define condição de parada para o build
  /status          Mostra fase, spec e agente
  /agents          Lista agentes carregados
  /workspace       Resumo do projeto
  /graph           Exporta o grafo de conhecimento
  /help            Esta ajuda
  sair             Encerra a sessão

Agentes: architect, frontend, backend, logic, reviewer, tester, generalista
""".strip()
