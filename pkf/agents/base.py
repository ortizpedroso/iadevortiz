from __future__ import annotations

import json
import re
import uuid
from typing import TYPE_CHECKING

import networkx as nx
from openai import AsyncOpenAI

from pkf.config import MAX_TOOL_ROUNDS, NODE_LIMIT
from pkf.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from pkf.router import Router

TOOL_BLOCK = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)
TOOL_FENCE = re.compile(r"```(?:tool|tool_call)\s*(\{.*?\})\s*```", re.S)
TOOL_FUNCTION = re.compile(
    r"<function=([a-z_]+)>\s*(\{.*?\})\s*</function>",
    re.S | re.I,
)


class Agent:
    def __init__(
        self,
        name: str,
        client: AsyncOpenAI,
        model: str,
        system_prompt: str,
        router: "Router",
        tools: ToolRegistry | None = None,
        supports_tools: bool = True,
    ):
        self.name = name
        self.client = client
        self.model = model
        self.router = router
        self.tools = tools
        self.supports_tools = supports_tools and tools is not None and bool(tools.tool_names)
        self.messages: list[dict] = [{"role": "system", "content": system_prompt}]
        self.graph = nx.DiGraph()
        self.node_counter = 0

    async def process(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": user_input})
        self.node_counter += 1
        user_node = f"user_{self.node_counter}"
        self.graph.add_node(user_node, role="user", content=user_input[:300], type="user_query")

        print(f"Agente '{self.name}' está trabalhando...")
        await self.router.emit("thinking", agent=self.name)
        reply = await self._complete_with_tools()

        self.node_counter += 1
        assistant_node = f"assistant_{self.node_counter}"
        self.graph.add_node(
            assistant_node,
            role="assistant",
            content=(reply or "")[:300],
            type="assistant_response",
        )
        self.graph.add_edge(user_node, assistant_node, relation="responds_to")
        await self._cluster_nodes_if_needed()
        return reply or ""

    async def _complete_with_tools(self) -> str:
        native_tools = self.supports_tools
        for _ in range(MAX_TOOL_ROUNDS):
            api_args: dict = {"model": self.model, "messages": self.messages}
            if native_tools:
                api_args["tools"] = self.tools.schemas()
            try:
                completion = await self.client.chat.completions.create(**api_args)
            except Exception as exc:
                if native_tools and _looks_like_tool_unsupported(exc):
                    native_tools = False
                    continue
                raise

            message = completion.choices[0].message
            tool_calls = list(_iter_native_tool_calls(message))
            content = message.content or ""
            if not tool_calls:
                tool_calls = parse_text_tool_calls(content)

            if not tool_calls:
                self.messages.append(_assistant_dict(message, content))
                return content

            self.messages.append(_assistant_dict(message, content, tool_calls if native_tools else None))
            for call in tool_calls:
                print(f"[tool:{self.name}] {call['name']} {call['arguments']}")
                await self.router.emit(
                    "tool",
                    agent=self.name,
                    name=call["name"],
                    arguments=call["arguments"],
                    status="running",
                )
                result = self.tools.execute(call["name"], call["arguments"]) if self.tools else "Sem ferramentas."
                await self.router.emit(
                    "tool",
                    agent=self.name,
                    name=call["name"],
                    arguments=call["arguments"],
                    status="done",
                    result=result[:800],
                )
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": result[:8000],
                    }
                )
                if not native_tools:
                    self.messages.append(
                        {
                            "role": "user",
                            "content": f"Resultado de {call['name']}:\n{result[:8000]}",
                        }
                    )
        return "Limite de ferramentas atingido. Resuma o que já foi feito e peça o próximo passo."

    async def _cluster_nodes_if_needed(self) -> None:
        text_messages = [m for m in self.messages if m.get("role") in {"user", "assistant"} and m.get("content")]
        if len(text_messages) == 0 or len(text_messages) % NODE_LIMIT != 0:
            return

        print(f"\n[Memória '{self.name}']: compactando {NODE_LIMIT} mensagens em um agente especialista...")
        to_summarize = text_messages[-NODE_LIMIT:]
        summary_messages = [
            {
                "role": "system",
                "content": (
                    "Resuma pontos-chave, decisões, arquivos e entidades desta conversa em um parágrafo. "
                    "Esse texto será o conhecimento de um agente de memória."
                ),
            },
            *[{"role": m["role"], "content": m.get("content", "")} for m in to_summarize],
        ]
        completion = await self.client.chat.completions.create(model=self.model, messages=summary_messages)
        summary = (completion.choices[0].message.content or "").strip()
        if not summary:
            return

        start = self.node_counter - NODE_LIMIT + 1
        manager_name = f"memoria_{self.name}_{max(start, 1)}-{self.node_counter}"
        manager_prompt = (
            "Você é um agente de memória da PKF. Responda só com base neste resumo:\n"
            f"{summary}"
        )
        memory_agent = Agent(
            name=manager_name,
            client=self.client,
            model=self.model,
            system_prompt=manager_prompt,
            router=self.router,
            tools=None,
            supports_tools=False,
        )
        self.router.register_agent(memory_agent, summary)
        self.messages = [self.messages[0]] + [
            {
                "role": "system",
                "content": (
                    f"[Memória compactada dos nós {max(start, 1)}-{self.node_counter} "
                    f"movida para o agente '{manager_name}'.]"
                ),
            }
        ]


def _assistant_dict(message, content: str, tool_calls: list[dict] | None = None) -> dict:
    payload: dict = {"role": "assistant", "content": content}
    native = getattr(message, "tool_calls", None)
    if native:
        payload["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "{}",
                },
            }
            for tc in native
        ]
    elif tool_calls:
        payload["tool_calls"] = [
            {
                "id": call["id"],
                "type": "function",
                "function": {
                    "name": call["name"],
                    "arguments": json.dumps(call["arguments"], ensure_ascii=False),
                },
            }
            for call in tool_calls
        ]
    return payload


def _iter_native_tool_calls(message) -> list[dict]:
    calls = []
    for tc in getattr(message, "tool_calls", None) or []:
        raw_args = tc.function.arguments or "{}"
        try:
            arguments = json.loads(raw_args)
        except json.JSONDecodeError:
            arguments = {}
        calls.append({"id": tc.id, "name": tc.function.name, "arguments": arguments})
    return calls


def parse_text_tool_calls(content: str) -> list[dict]:
    calls = []
    for block in (*TOOL_BLOCK.findall(content or ""), *TOOL_FENCE.findall(content or "")):
        call = _tool_call_from_json(block)
        if call:
            calls.append(call)
    for name, args in TOOL_FUNCTION.findall(content or ""):
        call = _tool_call_from_json(args, name=name)
        if call:
            calls.append(call)
    return calls


def _tool_call_from_json(block: str, name: str | None = None) -> dict | None:
    try:
        data = json.loads(block)
    except json.JSONDecodeError:
        return None
    tool_name = name or data.get("name")
    if not tool_name:
        return None
    arguments = data.get("arguments", data if name else {})
    if not isinstance(arguments, dict):
        arguments = {}
    return {"id": f"call_{uuid.uuid4().hex[:8]}", "name": tool_name, "arguments": arguments}


def _looks_like_tool_unsupported(exc: Exception) -> bool:
    text = str(exc).lower()
    return "tool" in text or "function" in text or "400" in text
