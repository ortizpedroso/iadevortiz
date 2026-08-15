from __future__ import annotations

from pathlib import Path

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from pkf.agents.base import Agent
from pkf.agents.developer import DeveloperAgent
from pkf.agents.prompts import AGENT_PROMPTS, DEVELOPER_AGENTS
from pkf.classifier import Intent, classify_intent, classify_intent_llm
from pkf.config import RELEVANCE_THRESHOLD, default_fallback
from pkf.memory.store import MemoryStore, export_graph
from pkf.spec.store import active_spec_preview
from pkf.providers import get_ai_client
from pkf.tools.registry import ToolRegistry, tools_for_agent
from pkf.workflow.cycle import DevCycle, parse_command
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
    ):
        self.provider_name = provider_name
        self.workspace = workspace
        self.fallback_provider = fallback_provider if fallback_provider is not None else default_fallback(provider_name)
        if client is None:
            client, config = get_ai_client(provider_name)
            model = config.model
            supports_tools = config.supports_tools
        self.client = client
        self.model_to_use = model or "llama3:8b"
        self.supports_tools = supports_tools
        self.memory = MemoryStore(workspace.root)
        self.cycle = DevCycle.load(workspace.root)
        self.agents: dict[str, Agent] = {}
        self._event_handler = None
        self._register_core_agents()
        self._restore_memory_agents()

    def set_event_handler(self, handler) -> None:
        self._event_handler = handler

    async def emit(self, event_type: str, **payload) -> None:
        if self._event_handler:
            await self._event_handler({"type": event_type, **payload})

    def snapshot(self) -> dict:
        preview = active_spec_preview(self.workspace.root, self.cycle.active_spec)
        return {
            "provider": self.provider_name,
            "model": self.model_to_use,
            "workspace": str(self.workspace.root),
            "phase": self.cycle.phase,
            "active_spec": self.cycle.active_spec,
            "spec_status": self.cycle.spec_status,
            "spec_preview": preview,
            "last_agent": self.cycle.last_agent,
            "agents": list(AGENT_PROMPTS),
        }

    def reset_conversation(self) -> None:
        for agent in self.agents.values():
            if agent.messages:
                agent.messages = [agent.messages[0]]
        self.cycle = DevCycle()
        self.cycle.persist(self.workspace.root)

    def _register_core_agents(self) -> None:
        context = self.workspace.scan_summary()
        for name, prompt in AGENT_PROMPTS.items():
            system_prompt = f"{prompt}\n\nContexto do projeto:\n{context}"
            tools = ToolRegistry(self.workspace, tools_for_agent(name))
            cls = DeveloperAgent if name in DEVELOPER_AGENTS else Agent
            self.agents[name] = cls(
                name=name,
                client=self.client,
                model=self.model_to_use,
                system_prompt=system_prompt,
                router=self,
                tools=tools,
                supports_tools=self.supports_tools,
            )

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
                    return (
                        "A spec precisa ser aprovada antes do /build. "
                        "Revise o painel à direita, ajuste a stack se quiser e clique em Aprovar."
                    )

        intent = await self._classify(user_input)
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
        reply = await agent.process(payload)
        self.cycle = DevCycle.load(self.workspace.root)
        preview = active_spec_preview(self.workspace.root, self.cycle.active_spec)
        if preview and preview.get("status") == "pending_approval":
            await self.emit("spec_preview", spec=preview)
        return reply

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
  /build [nome]    Implementa a spec ativa
  /review          Revisa o código contra a spec
  /status          Mostra fase, spec e agente
  /agents          Lista agentes carregados
  /workspace       Resumo do projeto
  /graph           Exporta o grafo de conhecimento
  /help            Esta ajuda
  sair             Encerra a sessão

Agentes: architect, frontend, backend, logic, reviewer, tester, generalista
""".strip()
