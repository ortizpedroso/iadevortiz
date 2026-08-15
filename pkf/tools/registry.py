from __future__ import annotations

from dataclasses import dataclass

from pkf.tools.impl import dispatch, parse_arguments
from pkf.workspace import Workspace

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
    "search_code": {
        "description": "Busca um padrão regex no código do workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "path": {"type": "string", "description": "Pasta ou arquivo inicial."},
            },
            "required": ["query"],
        },
    },
    "run_command": {
        "description": "Executa um comando permitido (python, pytest, npm, git status/diff/log, ruff, mypy).",
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
        "description": "Resumo do workspace: stack e arquivos de primeiro nível.",
        "parameters": {"type": "object", "properties": {}},
    },
}

AGENT_TOOLS = {
    "architect": ["project_context", "list_dir", "read_file", "search_code", "get_spec", "save_spec"],
    "frontend": [
        "project_context",
        "list_dir",
        "read_file",
        "write_file",
        "search_code",
        "run_command",
        "get_spec",
        "save_spec",
    ],
    "backend": [
        "project_context",
        "list_dir",
        "read_file",
        "write_file",
        "search_code",
        "run_command",
        "get_spec",
        "save_spec",
    ],
    "logic": [
        "project_context",
        "list_dir",
        "read_file",
        "write_file",
        "search_code",
        "run_command",
        "get_spec",
        "save_spec",
    ],
    "reviewer": [
        "project_context",
        "list_dir",
        "read_file",
        "search_code",
        "get_spec",
        "save_review",
    ],
    "tester": [
        "project_context",
        "list_dir",
        "read_file",
        "write_file",
        "search_code",
        "run_command",
        "get_spec",
    ],
    "generalista": ["project_context", "list_dir", "read_file", "search_code"],
}


@dataclass
class ToolCall:
    name: str
    arguments: dict
    call_id: str = ""


class ToolRegistry:
    def __init__(self, workspace: Workspace, tool_names: list[str]):
        self.workspace = workspace
        self.tool_names = [name for name in tool_names if name in TOOL_DEFINITIONS]

    def schemas(self) -> list[dict]:
        return openai_tool_schemas(self.tool_names)

    def execute(self, name: str, arguments) -> str:
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


def tools_for_agent(agent_name: str) -> list[str]:
    if agent_name.startswith("memoria_"):
        return []
    return AGENT_TOOLS.get(agent_name, AGENT_TOOLS["generalista"])
