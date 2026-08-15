from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from pkf.config import COMMAND_TIMEOUT, MAX_FILE_BYTES, MAX_SEARCH_MATCHES, pkf_dir
from pkf.spec.document import parse_spec
from pkf.graph.project import ProjectGraph
from pkf.spec.store import save_spec_document
from pkf.workspace import Workspace, WorkspaceError
from pkf.workspace_index import build_code_index, query_code_index, record_change, verify_workspace_files

ALLOWED_COMMANDS = (
    "python",
    "py",
    "pytest",
    "pip",
    "npm",
    "npx",
    "node",
    "git",
    "ruff",
    "mypy",
)

ALLOWED_GIT = {"status", "diff", "log", "branch", "show", "rev-parse"}
BLOCKED_TOKENS = {
    "rm -rf",
    "del /f",
    "format ",
    "shutdown",
    "reg ",
    "curl ",
    "wget ",
    "ssh ",
    "scp ",
    "powershell -enc",
    "invoke-webrequest",
    "npm publish",
    "pip install",
}


def _slug(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower()).strip("-")
    return cleaned or "spec"


def list_dir(workspace: Workspace, path: str = ".") -> str:
    target = workspace.resolve(path)
    if not target.exists():
        return f"Diretório não encontrado: {path}"
    if not target.is_dir():
        return f"Não é um diretório: {path}"
    rows: list[str] = []
    for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if workspace.is_ignored(child) or workspace.is_secret(child):
            continue
        suffix = "/" if child.is_dir() else ""
        rows.append(f"{child.name}{suffix}")
    return "\n".join(rows) or "(vazio)"


def read_file(workspace: Workspace, path: str) -> str:
    target = workspace.resolve(path)
    if workspace.is_secret(target):
        return "Arquivo bloqueado: contém credenciais."
    if not target.exists() or not target.is_file():
        return f"Arquivo não encontrado: {path}"
    data = target.read_bytes()
    if len(data) > MAX_FILE_BYTES:
        return f"Arquivo grande demais ({len(data)} bytes). Leia uma parte menor ou outro arquivo."
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "Arquivo binário; não é possível ler como texto."
    return text


def write_file(workspace: Workspace, path: str, content: str) -> str:
    target = workspace.resolve(path)
    if workspace.is_secret(target):
        return "Escrita bloqueada: arquivo de credenciais."
    rel = workspace.rel(target)
    allowed_internal = rel.startswith(".pkf/specs/") or rel.startswith(".pkf/reviews/")
    if workspace.is_ignored(target) and not allowed_internal:
        return f"Escrita bloqueada em caminho ignorado: {path}"
    action = "create" if not target.exists() else "overwrite"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    record_change(workspace, rel, action, content[:300])
    return f"Arquivo gravado: {rel} ({len(content)} caracteres)"


def edit_file(
    workspace: Workspace,
    path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> str:
    target = workspace.resolve(path)
    if workspace.is_secret(target):
        return "Edição bloqueada: arquivo de credenciais."
    rel = workspace.rel(target)
    allowed_internal = rel.startswith(".pkf/specs/") or rel.startswith(".pkf/reviews/")
    if workspace.is_ignored(target) and not allowed_internal:
        return f"Edição bloqueada em caminho ignorado: {path}"
    if not target.exists() or not target.is_file():
        return f"Arquivo não encontrado: {path}"
    content = target.read_text(encoding="utf-8")
    if old_string not in content:
        return f"Trecho não encontrado em {path}. Leia o arquivo e tente de novo."
    count = content.count(old_string) if replace_all else min(1, content.count(old_string))
    new_content = content.replace(old_string, new_string, count if replace_all else 1)
    target.write_text(new_content, encoding="utf-8", newline="\n")
    rel = workspace.rel(target)
    record_change(workspace, rel, "edit", new_string[:300])
    return f"Editado {rel}: {count} substituição(ões)."


def search_code(workspace: Workspace, query: str, path: str = ".") -> str:
    start = workspace.resolve(path)
    if not start.exists():
        return f"Caminho não encontrado: {path}"
    pattern = re.compile(query, re.IGNORECASE)
    matches: list[str] = []
    files = workspace.iter_files(start if start.is_dir() else start.parent)
    for file_path in files:
        if start.is_file() and file_path != start:
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                matches.append(f"{workspace.rel(file_path)}:{idx}: {line.strip()}")
                if len(matches) >= MAX_SEARCH_MATCHES:
                    return "\n".join(matches)
    return "\n".join(matches) or "Nenhum resultado."


def run_command(workspace: Workspace, command: str) -> str:
    cleaned = " ".join(command.strip().split())
    lower = cleaned.lower()
    if any(token in lower for token in BLOCKED_TOKENS):
        return "Comando bloqueado por segurança."
    parts = cleaned.split()
    if not parts:
        return "Comando vazio."
    binary = Path(parts[0]).name.lower()
    if binary not in ALLOWED_COMMANDS:
        return f"Comando não permitido: {binary}. Use as ferramentas de arquivo ou um comando da allowlist."
    if binary == "git":
        sub = parts[1] if len(parts) > 1 else ""
        if sub not in ALLOWED_GIT:
            return "Git permitido apenas para status, diff, log, branch, show e rev-parse."
    try:
        completed = subprocess.run(
            cleaned,
            cwd=workspace.root,
            shell=True,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return f"Comando excedeu {COMMAND_TIMEOUT}s."
    output = (completed.stdout or "") + (completed.stderr or "")
    output = output.strip() or "(sem saída)"
    return f"exit={completed.returncode}\n{output[:8000]}"


def get_spec(workspace: Workspace, name: str = "") -> str:
    specs_dir = pkf_dir(workspace.root) / "specs"
    if name:
        target = specs_dir / f"{_slug(name)}.md"
        if not target.exists():
            return f"Spec não encontrada: {name}"
        return target.read_text(encoding="utf-8")
    files = sorted(specs_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return "Nenhuma spec salva ainda."
    listing = "\n".join(f"- {p.stem}" for p in files)
    latest = files[0].read_text(encoding="utf-8")
    return f"Specs disponíveis:\n{listing}\n\n--- spec mais recente ({files[0].stem}) ---\n{latest}"


def save_spec(workspace: Workspace, name: str, content: str) -> str:
    if not content.strip():
        return "Spec vazia: inclua requisitos e stack sugerida."
    doc = parse_spec(content)
    if doc.title == "Spec" and name:
        doc.title = name.replace("-", " ").title()
    slug = _slug(name or doc.title)
    if doc.status not in {"pending_approval", "approved", "draft"}:
        doc.status = "pending_approval"
    path = save_spec_document(workspace.root, slug, doc)
    return (
        f"Spec salva em {workspace.rel(path)} (status: {doc.status}). "
        "O usuário verá a spec na tela para revisar e aprovar antes do /build."
    )


def save_review(workspace: Workspace, name: str, content: str) -> str:
    reviews_dir = pkf_dir(workspace.root) / "reviews"
    target = reviews_dir / f"{_slug(name)}.md"
    target.write_text(content, encoding="utf-8", newline="\n")
    return f"Review salva em {workspace.rel(target)}"


def project_context(workspace: Workspace) -> str:
    graph = ProjectGraph(workspace.root)
    base = workspace.scan_summary()
    return f"{base}\n\n{graph.summary()}"


def graph_view(workspace: Workspace) -> str:
    return ProjectGraph(workspace.root).summary()


def graph_assign_file(workspace: Workspace, node_id: str, path: str) -> str:
    graph = ProjectGraph(workspace.root)
    if node_id not in graph.nodes:
        return f"Nó '{node_id}' não existe. Use graph_view."
    graph.assign_file(node_id, path)
    return f"Arquivo {path} associado ao nó {node_id}."


def graph_add_node(workspace: Workspace, node_id: str, parent: str, labels: list) -> str:
    graph = ProjectGraph(workspace.root)
    if not isinstance(labels, list):
        labels = [str(labels)]
    node = graph.maybe_cluster_labels(parent, [str(x) for x in labels])
    if not node:
        return f"Necessários pelo menos 3 itens relacionados para criar nó dinâmico."
    return f"Nó dinâmico '{node.id}' criado sob '{parent}'."


def verify_build(workspace: Workspace) -> str:
    result = verify_workspace_files(workspace)
    if not result["ok"]:
        return "Build incompleto: nenhum arquivo gerado no workspace."
    return f"Build verificado: {result['count']} arquivo(s). Exemplos: {', '.join(result['files'][:8])}"


def code_index(workspace: Workspace, query: str = "") -> str:
    if query:
        return query_code_index(workspace, query)
    return build_code_index(workspace)


def dispatch(workspace: Workspace, name: str, arguments: dict) -> str:
    try:
        if name == "list_dir":
            return list_dir(workspace, arguments.get("path", "."))
        if name == "read_file":
            return read_file(workspace, arguments["path"])
        if name == "write_file":
            return write_file(workspace, arguments["path"], arguments.get("content", ""))
        if name == "edit_file":
            return edit_file(
                workspace,
                arguments["path"],
                arguments["old_string"],
                arguments.get("new_string", ""),
                bool(arguments.get("replace_all")),
            )
        if name == "search_code":
            return search_code(workspace, arguments["query"], arguments.get("path", "."))
        if name == "run_command":
            return run_command(workspace, arguments["command"])
        if name == "get_spec":
            return get_spec(workspace, arguments.get("name", ""))
        if name == "save_spec":
            return save_spec(workspace, arguments["name"], arguments.get("content", ""))
        if name == "save_review":
            return save_review(workspace, arguments["name"], arguments.get("content", ""))
        if name == "project_context":
            return project_context(workspace)
        if name == "graph_view":
            return graph_view(workspace)
        if name == "graph_assign_file":
            return graph_assign_file(workspace, arguments["node_id"], arguments["path"])
        if name == "graph_add_node":
            return graph_add_node(
                workspace,
                arguments.get("node_id", ""),
                arguments.get("parent", "frontend"),
                arguments.get("labels", []),
            )
        if name == "verify_build":
            return verify_build(workspace)
        if name == "code_index":
            return code_index(workspace, arguments.get("query", ""))
        return f"Ferramenta desconhecida: {name}"
    except (KeyError, TypeError) as exc:
        return f"Argumentos inválidos para {name}: {exc}"
    except WorkspaceError as exc:
        return str(exc)
    except OSError as exc:
        return f"Erro de I/O: {exc}"


def parse_arguments(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}
