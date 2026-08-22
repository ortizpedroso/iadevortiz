from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pkf.tools.impl import dispatch, parse_arguments
from pkf.workspace import Workspace

if TYPE_CHECKING:
    from pkf.router import Router

_WRITE_TOOLS = frozenset({"write_file", "edit_file"})

_SHARED_CORE = [
    "project_context",
    "list_dir",
    "read_file",
    "write_file",
    "edit_file",
    "get_spec",
    "graph_assign_file",
    "verify_build",
]

_SHARED_OPTIONAL = [
    "search_code",
    "code_index",
    "run_command",
    "graph_view",
    "graph_add_node",
    "save_spec",
    "skill_search",
    "web_search",
]

_SHARED_DEV = _SHARED_CORE + _SHARED_OPTIONAL

TOOL_DEFINITIONS: dict[str, dict] = {
    "list_dir": {
        "description": "Lista arquivos e pastas de um diretório do workspace.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Caminho relativo. Padrão: ."}},
        },
    },
    "read_file": {
        "description": "Lê um arquivo de texto do workspace.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    "write_file": {
        "description": "Cria ou sobrescreve um arquivo de texto no workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    "edit_file": {
        "description": "Substitui um trecho em arquivo existente (preferível a reescrever tudo).",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
                "replace_all": {"type": "boolean"},
            },
            "required": ["path", "old_string", "new_string"],
        },
    },
    "search_code": {
        "description": "Busca no código: mode=text (regex) ou mode=semantic (similaridade por significado).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "path": {"type": "string", "description": "Pasta ou arquivo inicial."},
                "mode": {
                    "type": "string",
                    "enum": ["text", "semantic"],
                    "description": "text=regex; semantic=busca por significado (índice local).",
                },
            },
            "required": ["query"],
        },
    },
    "code_index": {
        "description": "Indexa o codebase ou busca no índice (query opcional).",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
        },
    },
    "run_command": {
        "description": (
            "Executa um comando permitido (python, pytest, npm, git status/diff/log, ruff, mypy). "
            "Pipes e encadeamento (&&, ;, |) não são suportados por design."
        ),
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    "get_spec": {
        "description": "Lê uma spec salva em .pkf/specs. Sem nome, lista e devolve a mais recente.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        },
    },
    "save_spec": {
        "description": "Salva ou atualiza uma especificação em .pkf/specs.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["name", "content"],
        },
    },
    "save_review": {
        "description": "Salva um relatório de review em .pkf/reviews.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["name", "content"],
        },
    },
    "project_context": {
        "description": "Resumo do workspace, stack e grafo do projeto.",
        "parameters": {"type": "object", "properties": {}},
    },
    "graph_view": {
        "description": "Mostra nós do grafo do projeto (frontend, backend, dinâmicos).",
        "parameters": {"type": "object", "properties": {}},
    },
    "graph_assign_file": {
        "description": "Associa um arquivo a um nó do grafo.",
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["node_id", "path"],
        },
    },
    "graph_add_node": {
        "description": "Cria nó dinâmico quando há 3+ itens relacionados.",
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "parent": {"type": "string"},
                "labels": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["parent", "labels"],
        },
    },
    "verify_build": {
        "description": "Verifica se arquivos foram gerados no workspace após build.",
        "parameters": {
            "type": "object",
            "properties": {
                "phase": {
                    "type": "string",
                    "description": "Fase da verificação (padrão: T3).",
                }
            },
        },
    },
    "get_last_verification": {
        "description": (
            "Retorna o resultado real persistido da última verificação de build "
            "(fase T3): timestamp, sucesso/falha e mensagem completa."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    "get_build_status": {
        "description": (
            "Retorna o progresso atual do build: fase do ciclo, spec ativa, árvore de tarefas "
            "(agentes done/running/pending), última verificação T3 e checkpoint."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    "skill_search": {
        "description": "Busca skills Markdown por relevância BM25 e auto-carrega a melhor.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    "web_search": {
        "description": "Busca na web (Tavily ou Brave). Requer TAVILY_API_KEY ou BRAVE_SEARCH_API_KEY no .env.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "description": "1–10, padrão 5"},
            },
            "required": ["query"],
        },
    },
}

AGENT_TOOLS = {
    "architect": [
        "project_context",
        "list_dir",
        "read_file",
        "search_code",
        "code_index",
        "web_search",
        "get_spec",
        "save_spec",
        "graph_view",
        "graph_add_node",
    ],
    "frontend": _SHARED_CORE,
    "backend": _SHARED_CORE,
    "logic": _SHARED_CORE,
    "reviewer": [
        "project_context",
        "list_dir",
        "read_file",
        "search_code",
        "code_index",
        "get_spec",
        "get_last_verification",
        "save_review",
        "graph_view",
        "verify_build",
    ],
    "tester": [
        "project_context",
        "list_dir",
        "read_file",
        "write_file",
        "edit_file",
        "search_code",
        "run_command",
        "get_spec",
        "verify_build",
    ],
    "generalista": [
        "project_context",
        "list_dir",
        "read_file",
        "search_code",
        "web_search",
        "graph_view",
        "get_last_verification",
        "get_build_status",
    ],
}


@dataclass
class ToolCall:
    name: str
    arguments: dict
    call_id: str = ""


class ToolRegistry:
    def __init__(
        self,
        workspace: Workspace,
        tool_names: list[str],
        optional: list[str] | None = None,
        router: Router | None = None,
    ):
        self.workspace = workspace
        self.router = router
        self.tool_names = [name for name in tool_names if name in TOOL_DEFINITIONS]
        agent_optional = optional if optional is not None else _SHARED_OPTIONAL
        self._optional = [n for n in agent_optional if n in TOOL_DEFINITIONS]

    def maybe_expand(self, name: str) -> None:
        if name in self.tool_names:
            return
        if name in self._optional and name not in self.tool_names:
            self.tool_names.append(name)

    def schemas(self) -> list[dict]:
        names = list(dict.fromkeys(self.tool_names + self._optional))
        return openai_tool_schemas(names)

    def _rel_tool_path(self, path: str) -> str:
        return self.workspace.rel(self.workspace.resolve(path))

    async def execute_async(self, name: str, arguments) -> str:
        if name not in self.tool_names and name in self._optional:
            self.tool_names.append(name)
        if name not in self.tool_names:
            return f"Ferramenta '{name}' não disponível para este agente."
        args = parse_arguments(arguments)
        if name in _WRITE_TOOLS:
            path = args.get("path", "")
            if path:
                rel = self._rel_tool_path(path)
                lock = self.workspace.file_lock(rel)
                if lock.locked() and self.router:
                    await self.router.emit(
                        "tool",
                        agent=getattr(self.router, "_active_agent", None),
                        name=name,
                        info=f"aguardando lock em {rel}",
                        status="waiting",
                    )
                async with lock:
                    return dispatch(self.workspace, name, args)
        return dispatch(self.workspace, name, args)

    def execute(self, name: str, arguments) -> str:
        if name not in self.tool_names and name in self._optional:
            self.tool_names.append(name)
        if name not in self.tool_names:
            return f"Ferramenta '{name}' não disponível para este agente."
        return dispatch(self.workspace, name, parse_arguments(arguments))


def openai_tool_schemas(tool_names: list[str]) -> list[dict]:
    schemas = []
    for name in tool_names:
        spec = TOOL_DEFINITIONS[name]
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": spec["description"],
                    "parameters": spec["parameters"],
                },
            }
        )
    return schemas


def tools_for_agent(agent_name: str) -> tuple[list[str], list[str]]:
    if agent_name.startswith("memoria_"):
        return [], []
    names = AGENT_TOOLS.get(agent_name, AGENT_TOOLS["generalista"])
    core = [n for n in names if n in _SHARED_CORE or n not in _SHARED_OPTIONAL]
    optional = [n for n in _SHARED_OPTIONAL if n not in core]
    return core, optional
