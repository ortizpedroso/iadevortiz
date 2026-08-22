from __future__ import annotations

import ast
import contextlib
import difflib
import json
import os
import re
import shlex
import subprocess
from pathlib import Path

from pkf.config import COMMAND_TIMEOUT, MAX_FILE_BYTES, MAX_SEARCH_MATCHES, is_production, is_secret_env_var, pkf_dir
from pkf.graph.project import ProjectGraph
from pkf.semantic_index import update_file_index
from pkf.skills.search import skill_search_tool_output
from pkf.spec.document import parse_spec, parse_spec_meta, validate_suggested_stack
from pkf.spec.store import save_spec_document
from pkf.verify_store import load_last_verification, save_last_verification
from pkf.web_search import web_search
from pkf.workspace import Workspace, WorkspaceError
from pkf.workspace_index import (
    build_code_index,
    query_code_index,
    record_change,
    verify_workspace_files,
)

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
SHELL_CHAINING = ("&&", ";", "|", "`", "$(", ">", "<")
MAX_COMMAND_OUTPUT = 10_000


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


def _validate_syntax(rel_path: str, content: str) -> str | None:
    suffix = Path(rel_path).suffix.lower()
    if suffix == ".py":
        try:
            ast.parse(content)
        except SyntaxError as exc:
            return f"Erro de sintaxe Python: {exc}"
    elif suffix == ".json":
        try:
            json.loads(content)
        except json.JSONDecodeError as exc:
            return f"JSON inválido: {exc}"
    return None


def _short_unified_diff(old: str, new: str, rel_path: str, max_lines: int = 24) -> str:
    diff_lines = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{rel_path}",
        tofile=f"b/{rel_path}",
        lineterm="",
    )
    return "".join(list(diff_lines)[:max_lines])[:800]


def _update_impact_graph(workspace: Workspace, rel: str, target: Path) -> None:
    from pkf.utils.impact_graph import bfs_affected_files, register_file, store_review_scope

    register_file(workspace.root, rel, target)
    affected = bfs_affected_files(workspace.root, rel)
    store_review_scope(workspace.root, affected)


def write_file(workspace: Workspace, path: str, content: str) -> str:
    target = workspace.resolve(path)
    if workspace.is_secret(target):
        return "Escrita bloqueada: arquivo de credenciais."
    rel = workspace.rel(target)
    allowed_internal = rel.startswith((".pkf/specs/", ".pkf/reviews/"))
    if workspace.is_ignored(target) and not allowed_internal:
        return f"Escrita bloqueada em caminho ignorado: {path}"
    existed = target.exists()
    original = target.read_text(encoding="utf-8") if existed else None
    action = "create" if not existed else "overwrite"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    syntax_error = _validate_syntax(rel, content)
    if syntax_error:
        if existed and original is not None:
            target.write_text(original, encoding="utf-8", newline="\n")
        elif target.exists():
            target.unlink()
        return f"{syntax_error} Escrita revertida."
    record_change(workspace, rel, action, content[:300])
    with contextlib.suppress(OSError, ValueError, RuntimeError):
        update_file_index(workspace, rel)
    _update_impact_graph(workspace, rel, target)
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
    allowed_internal = rel.startswith((".pkf/specs/", ".pkf/reviews/"))
    if workspace.is_ignored(target) and not allowed_internal:
        return f"Edição bloqueada em caminho ignorado: {path}"
    if not target.exists() or not target.is_file():
        return f"Arquivo não encontrado: {path}"
    if old_string == new_string:
        return "Nenhuma mudança: old_string e new_string são idênticos."
    content = target.read_text(encoding="utf-8")
    if old_string not in content:
        return f"Trecho não encontrado em {path}. Leia o arquivo e tente de novo."
    occurrences = content.count(old_string)
    if occurrences > 1 and not replace_all:
        return (
            f"Trecho ambíguo em {path}: aparece {occurrences} vezes. "
            "Inclua mais contexto para torná-lo único, ou use replace_all=true."
        )
    count = occurrences if replace_all else 1
    new_content = content.replace(old_string, new_string, count)
    target.write_text(new_content, encoding="utf-8", newline="\n")
    syntax_error = _validate_syntax(rel, new_content)
    if syntax_error:
        target.write_text(content, encoding="utf-8", newline="\n")
        return f"{syntax_error} Edição revertida."
    diff = _short_unified_diff(content, new_content, rel)
    audit = f"old={old_string[:120]!r} new={new_string[:120]!r}\n{diff}"
    record_change(workspace, rel, "edit", audit)
    with contextlib.suppress(OSError, ValueError, RuntimeError):
        update_file_index(workspace, rel)
    _update_impact_graph(workspace, rel, target)
    return f"Editado {rel}: {count} substituição(ões)."


MAX_REGEX_PATTERN_LEN = 200


def search_code(workspace: Workspace, query: str, path: str = ".", mode: str = "text") -> str:
    if (mode or "text").lower() == "semantic":
        from pkf.semantic_index import semantic_search

        return semantic_search(workspace, query)
    if len(query) > MAX_REGEX_PATTERN_LEN:
        return f"Padrão regex muito longo (máx. {MAX_REGEX_PATTERN_LEN} caracteres)."
    start = workspace.resolve(path)
    if not start.exists():
        return f"Caminho não encontrado: {path}"
    try:
        pattern = re.compile(query, re.IGNORECASE)
    except re.error as exc:
        return f"Padrão regex inválido: {exc}"
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


def _safe_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in list(env):
        if is_secret_env_var(key):
            env.pop(key, None)
    return env


def _truncate_output(text: str, limit: int = MAX_COMMAND_OUTPUT) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n… (saída truncada em {limit} caracteres)"


def run_command(workspace: Workspace, command: str) -> str:
    raw = command.strip()
    if not raw:
        return "Comando vazio."
    if is_production() and os.getenv("PKF_ALLOW_RUN_COMMAND", "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        return (
            "run_command desabilitado em PKF_ENV=production. "
            "Defina PKF_ALLOW_RUN_COMMAND=1 no .env se precisar executar testes na VPS."
        )
    for token in SHELL_CHAINING:
        if token in raw:
            return (
                f"Comando bloqueado: encadeamento '{token}' não é suportado. "
                "Use um único comando por vez."
            )
    try:
        parts = shlex.split(raw, posix=os.name != "nt")
    except ValueError as exc:
        return f"Comando inválido: {exc}"
    if not parts:
        return "Comando vazio."
    binary = Path(parts[0]).name.lower()
    binary = binary.removesuffix(".exe")
    if binary not in ALLOWED_COMMANDS:
        return f"Comando não permitido: {binary}. Use as ferramentas de arquivo ou um comando da allowlist."
    if binary == "git":
        sub = parts[1] if len(parts) > 1 else ""
        if sub not in ALLOWED_GIT:
            return "Git permitido apenas para status, diff, log, branch, show e rev-parse."
    try:
        completed = subprocess.run(
            parts,
            cwd=workspace.root,
            shell=False,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            env=_safe_subprocess_env(),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return f"Comando excedeu {COMMAND_TIMEOUT}s."
    stdout = _truncate_output(completed.stdout or "")
    stderr = _truncate_output(completed.stderr or "")
    output = (stdout + stderr).strip() or "(sem saída)"
    return f"exit={completed.returncode}\n{output}"


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
    meta = parse_spec_meta(content)
    used_name_fallback = doc.title == "Spec" and bool(name.strip())
    if used_name_fallback:
        if len(re.findall(r"\S+", name.strip())) > 8:
            return (
                "Erro: o nome da spec parece ser uma frase/comando do usuário, não um título de projeto. "
                "Use um título curto e descritivo (ex.: 'Cardápio Digital Whitelabel') no campo title "
                "do frontmatter e no parâmetro name."
            )
        doc.title = name.replace("-", " ").title()
    stack_error = validate_suggested_stack(meta, doc.suggested_stack)
    if stack_error:
        return f"Erro ao salvar spec: {stack_error}"
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
        return "Necessários pelo menos 3 itens relacionados para criar nó dinâmico."
    return f"Nó dinâmico '{node.id}' criado sob '{parent}'."


def verify_build(workspace: Workspace, phase: str = "T3") -> str:
    result = verify_workspace_files(workspace)
    if not result["ok"]:
        reason = result.get("reason")
        if reason == "no_build_session":
            text = "Build incompleto: sessão de build não iniciada."
        elif reason == "invalid_session":
            text = "Build incompleto: sessão de build inválida."
        else:
            text = "Build incompleto: nenhum arquivo gerado no workspace."
    else:
        text = f"Build verificado: {result['count']} arquivo(s). Exemplos: {', '.join(result['files'][:8])}"
    save_last_verification(
        workspace.root,
        phase=phase,
        ok=bool(result["ok"]),
        result=text,
        details=result,
    )
    return text


def get_build_status(workspace: Workspace) -> str:
    from pkf.workflow.cycle import DevCycle
    from pkf.workflow.tasks import TaskTracker

    cycle = DevCycle.load(workspace.root)
    lines = [
        "# Status do build",
        "",
        f"- Fase: {cycle.phase}",
        f"- Spec ativa: {cycle.active_spec or '(nenhuma)'}",
        f"- Status da spec: {cycle.spec_status or '(não definido)'}",
        f"- Meta (/goal): {cycle.goal or '(nenhuma)'}",
        f"- Último agente: {cycle.last_agent or '(nenhum)'}",
        "",
    ]

    tracker = TaskTracker(workspace.root)
    tasks = tracker.to_list()
    if tasks:
        lines.append("## Árvore de tarefas")
        lines.extend(_format_task_nodes(tasks[0], depth=0))
        statuses = tracker.agent_statuses()
        if statuses:
            lines.append("")
            lines.append("## Agentes")
            for agent, status in sorted(statuses.items()):
                lines.append(f"- {agent}: {status}")
    else:
        lines.append("Nenhum build em andamento registrado (tasks.json ausente ou vazio).")

    verify = load_last_verification(workspace.root)
    if verify:
        lines.append("")
        status = "sucesso" if verify.get("ok") else "falha"
        lines.append(f"## Última verificação ({verify.get('phase', 'T3')}) — {status}")
        lines.append(f"Timestamp: {verify.get('timestamp', 'desconhecido')}")
        result_text = str(verify.get("result") or "").strip()
        if result_text:
            lines.append(result_text[:800])

    checkpoint = pkf_dir(workspace.root) / "checkpoint.md"
    if checkpoint.exists():
        text = checkpoint.read_text(encoding="utf-8").strip()
        if text:
            lines.append("")
            lines.append("## Checkpoint")
            lines.append(text[:600])

    return "\n".join(lines)


def _format_task_nodes(node: dict, depth: int = 0) -> list[str]:
    indent = "  " * depth
    status = node.get("status", "pending")
    lines = [f"{indent}- [{status}] {node.get('title', node.get('id', '?'))}"]
    for child in node.get("children", []):
        lines.extend(_format_task_nodes(child, depth + 1))
    return lines


def get_last_verification(workspace: Workspace) -> str:
    data = load_last_verification(workspace.root)
    if not data:
        return "Nenhuma verificação de build registrada ainda."
    status = "sucesso" if data.get("ok") else "falha"
    lines = [
        f"Última verificação ({data.get('phase', 'T3')}) — {status}",
        f"Timestamp: {data.get('timestamp', 'desconhecido')}",
        "",
        str(data.get("result") or "").strip() or "(sem texto de resultado)",
    ]
    details = data.get("details")
    if isinstance(details, dict) and details.get("reason"):
        lines.append(f"\nMotivo técnico: {details['reason']}")
    if isinstance(details, dict) and details.get("files"):
        files = details["files"]
        if files:
            lines.append(f"Arquivos na sessão: {', '.join(files[:12])}")
    return "\n".join(lines)


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
            return search_code(
                workspace,
                arguments["query"],
                arguments.get("path", "."),
                arguments.get("mode", "text"),
            )
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
            return verify_build(workspace, arguments.get("phase", "T3"))
        if name == "get_last_verification":
            return get_last_verification(workspace)
        if name == "get_build_status":
            return get_build_status(workspace)
        if name == "code_index":
            return code_index(workspace, arguments.get("query", ""))
        if name == "skill_search":
            return skill_search_tool_output(arguments.get("query", ""))
        if name == "web_search":
            raw_max = arguments.get("max_results", 5) or 5
            try:
                max_results = int(raw_max)
            except (TypeError, ValueError):
                max_results = 5
            return web_search(arguments.get("query", ""), max_results)
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
