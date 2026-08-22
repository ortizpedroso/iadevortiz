"""Ciclo /build → /review programático contra spec pkf-platform."""

from __future__ import annotations

from pathlib import Path

from pkf.spec.updater import save_platform_spec
from pkf.web import server as web_server
from pkf.workflow.compose import MAX_REVIEW_FIX_CYCLES
from pkf.workflow.review import parse_review_status

SPEC_CHECKS = (
    ("Menu de contexto", "Menu de contexto"),
    ("PATCH rename", "PATCH /api/projects"),
    ("CSS vars", "--pkf-accent"),
    ("Headroom", "PKF_HEADROOM_PROXY_URL"),
    ("9Router skip 401", "401"),
    ("Router-only", "PKF_ROUTER_ONLY"),
    ("OmniRoute", "OmniRoute"),
    ("Tier qualidade", "PKF_TIER_QUALITY"),
    ("Build graph", "PKF_USE_LANGGRAPH_BUILD"),
    ("Benchmark", "benchmark"),
    ("Verificação T3", "get_last_verification"),
    ("Segurança produção", "Segurança e produção"),
    ("Memória anti-fabricação", "Memória de sessão"),
    ("Classificador", "Classificador de intenção"),
    ("Coerência /spec", "Coerência no /spec"),
    ("save_spec validação", "save_spec"),
    ("save_spec substância", "validate_spec_substance"),
    ("PATCH rename chat", "PATCH /api/chats"),
    ("Alembic deploy", "alembic upgrade head"),
    ("Auto-scroll chat", "Chat auto-scroll"),
    ("Composer largo", "max-w-4xl"),
    ("Auth token deploy", "não sobrescreve"),
    ("Preview isolado", "allow-same-origin"),
    ("Preview token", "preview_token"),
    ("WS subprotocol", "pkf-token."),
    ("OmniRoute API key", "REQUIRE_API_KEY"),
    ("Rate limiting", "Rate limiting"),
    ("Auth loopback", "PKF_REQUIRE_AUTH"),
    ("Scroll pausado", "Auto-scroll pausado"),
    ("DAG bloqueio falha", "bloqueia"),
    ("Handoff artifacts", "verificados via"),
    ("Memória lazy", "sob demanda"),
    ("Limite memória", "PKF_MEMORY_MAX_ENTRIES"),
    ("Validação DAG", "DagValidationError"),
    ("Auditoria agentes", "AUDITORIA_AGENTES"),
    ("DAG depends_on", "depends_on"),
    ("Handoff agentes", "handoff_context_for_deps"),
    ("Grafo impacto AST", "impact_graph"),
    ("Orquestrador DAG", "run_build_dag"),
    ("save_spec substância", "validate_spec_substance"),
    ("PATCH rename chat", "PATCH /api/chats"),
    ("Alembic deploy", "alembic upgrade head"),
)


def _implementation_gaps(spec_text: str) -> list[str]:
    gaps: list[str] = []
    for label, needle in SPEC_CHECKS:
        if needle not in spec_text:
            gaps.append(f"Spec sem: {label}")
    server_src = Path(web_server.__file__).read_text(encoding="utf-8")
    if "projects_rename" not in server_src and '@app.patch("/api/projects/{slug}")' not in server_src:
        gaps.append("Backend: PATCH /api/projects/{slug} ausente")
    sidebar = Path("frontend/src/components/Sidebar.tsx").read_text(encoding="utf-8")
    if "Renomear" not in sidebar or "onRenameProject" not in sidebar:
        gaps.append("Frontend: menu Renomear ausente")
    if "window.confirm" not in sidebar:
        gaps.append("Frontend: confirmacao de exclusao ausente")
    css = Path("frontend/src/index.css").read_text(encoding="utf-8")
    if "--pkf-accent" not in css:
        gaps.append("CSS: variaveis centralizadas ausentes")
    set_env = Path("deploy/hostinger/set-env-keys.sh").read_text(encoding="utf-8")
    if "if ! grep -q '^PKF_AUTH_TOKEN=' .env" not in set_env:
        gaps.append("Deploy: PKF_AUTH_TOKEN ainda sobrescrito a cada update")
    if "set_kv_default NINEROUTER_MODEL" not in set_env:
        gaps.append("Deploy: NINEROUTER_MODEL ainda sobrescrito em set-env-keys")
    update_sh = Path("deploy/hostinger/update.sh").read_text(encoding="utf-8")
    if "?token=$(grep '^PKF_AUTH_TOKEN='" in update_sh:
        gaps.append("Deploy: update.sh ainda imprime token na URL")
    if "alembic upgrade head" not in update_sh:
        gaps.append("Deploy: alembic upgrade head ausente em update.sh")
    preview_py = Path("pkf/web/preview.py").read_text(encoding="utf-8")
    if "?token=" in preview_py:
        gaps.append("Preview: redirect ainda inclui token na query")
    app_tsx = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    if "allow-same-origin" in app_tsx:
        gaps.append("Preview: iframe ainda usa allow-same-origin")
    if "shouldAutoScrollRef" not in app_tsx or "isNearChatBottom" not in app_tsx:
        gaps.append("Frontend: auto-scroll inteligente do chat ausente")
    if "scrollPaused" not in app_tsx or "Auto-scroll pausado" not in app_tsx:
        gaps.append("Frontend: indicador auto-scroll pausado ausente")
    api_ts = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")
    if "pkf-token." not in api_ts or "preview_token" not in api_ts:
        gaps.append("Frontend: WS subprotocol ou preview_token ausente em api.ts")
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    if 'REQUIRE_API_KEY: "true"' not in compose:
        gaps.append("Deploy: OmniRoute REQUIRE_API_KEY não está true")
    if "pkf-admin-2026" in compose:
        gaps.append("Deploy: senha OmniRoute fraca ainda no compose")
    deploy_yml = Path(".github/workflows/deploy.yml").read_text(encoding="utf-8")
    if "secrets.VPS_HOST" not in deploy_yml:
        gaps.append("Deploy: VPS_HOST secret ausente no workflow")
    if "187.77.240.125" in deploy_yml:
        gaps.append("Deploy: IP VPS ainda hardcoded no workflow")
    auth_py = Path("pkf/web/auth.py").read_text(encoding="utf-8")
    if "auth_enforced" not in auth_py or "preview_token" not in auth_py:
        gaps.append("Backend: auth_enforced ou preview_token ausente")
    if not Path("pkf/web/preview_tokens.py").is_file():
        gaps.append("Backend: preview_tokens.py ausente")
    if not Path("pkf/web/rate_limit.py").is_file():
        gaps.append("Backend: rate_limit.py ausente")
    if "validate_production_config" not in Path("pkf/web/server.py").read_text(encoding="utf-8"):
        gaps.append("Backend: validate_production_config ausente no boot")
    impl = Path("pkf/tools/impl.py").read_text(encoding="utf-8")
    if "validate_suggested_stack" not in impl:
        gaps.append("save_spec: validate_suggested_stack não integrado")
    if "frase/comando do usuário" not in impl:
        gaps.append("save_spec: validação de título longo ausente")
    if "validate_spec_substance" not in impl:
        gaps.append("save_spec: validate_spec_substance não integrado")
    if '"/api/chats/{chat_id}"' not in Path(web_server.__file__).read_text(encoding="utf-8") and "chats_rename" not in Path(web_server.__file__).read_text(encoding="utf-8"):
        gaps.append("Backend: PATCH /api/chats/{chat_id} ausente")
    if "onRenameChat" not in app_tsx:
        gaps.append("Frontend: onRenameChat ausente")
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    if "COPY alembic" not in dockerfile:
        gaps.append("Deploy: alembic/ não copiado no Dockerfile")
    classifier = Path("pkf/classifier.py").read_text(encoding="utf-8")
    if "_is_spec_complaint" not in classifier:
        gaps.append("Classificador: _is_spec_complaint ausente")
    architect = Path("pkf/agents/prompts.py").read_text(encoding="utf-8")
    if "CORRETO:" not in architect or "ERRADO:" not in architect:
        gaps.append("Arquiteto: few-shot uma pergunta vs lista ausente")
    if "sugira você" not in architect:
        gaps.append("Arquiteto: instrução de síntese ao delegar decisão ausente")
    composer = Path("frontend/src/components/Composer.tsx").read_text(encoding="utf-8")
    message_list = Path("frontend/src/components/MessageList.tsx").read_text(encoding="utf-8")
    if "max-w-4xl" not in composer:
        gaps.append("Frontend: Composer sem max-w-4xl")
    if "max-w-4xl" not in message_list:
        gaps.append("Frontend: MessageList sem max-w-4xl")
    orchestrator = Path("pkf/workflow/orchestrator.py").read_text(encoding="utf-8")
    if "_propagate_skipped_due_to_failed" not in orchestrator:
        gaps.append("Orquestrador: bloqueio de dependentes após falha (AUD-001) ausente")
    if "change_paths_since" not in orchestrator:
        gaps.append("Orquestrador: artifacts de handoff (AUD-002) ausente")
    if "run_build_dag" not in orchestrator:
        gaps.append("Orquestrador: run_build_dag ausente")
    if "handoff_context_for_deps" not in orchestrator:
        gaps.append("Orquestrador: handoff_context_for_deps não integrado")
    handoff = Path("pkf/workflow/handoff.py").read_text(encoding="utf-8")
    if 'get("status") == "failed"' not in handoff:
        gaps.append("Handoff: status failed (AUD-006) ausente")
    router_py = Path("pkf/router.py").read_text(encoding="utf-8")
    if "_ensure_memory_agent" not in router_py:
        gaps.append("Router: memória lazy (AUD-003) ausente")
    if "DagValidationError" not in router_py:
        gaps.append("Router: tratamento DagValidationError (AUD-004) ausente")
    if "load_review_scope" not in router_py:
        gaps.append("Router: escopo BFS do reviewer ausente")
    if "MEMORY_MAX_ENTRIES" not in Path("pkf/config.py").read_text(encoding="utf-8"):
        gaps.append("Config: PKF_MEMORY_MAX_ENTRIES (AUD-008) ausente")
    compact = Path("pkf/agents/compact.py").read_text(encoding="utf-8")
    if "workspace_root" not in compact or "changes.json" not in compact:
        gaps.append("Compact: contexto de arquivos verificados (AUD-007) ausente")
    if not Path("docs/AUDITORIA_AGENTES.md").is_file():
        gaps.append("Docs: AUDITORIA_AGENTES.md ausente")
    if not Path("specs/remediacao-auditoria-agentes.md").is_file():
        gaps.append("Spec: remediacao-auditoria-agentes.md ausente")
    if not Path("pkf/workflow/task_graph.py").is_file():
        gaps.append("Workflow: task_graph.py ausente")
    if not Path("pkf/workflow/handoff.py").is_file():
        gaps.append("Workflow: handoff.py ausente")
    planner = Path("pkf/workflow/planner.py").read_text(encoding="utf-8")
    if "AGENT_DEPENDS" not in planner or "depends_on" not in planner:
        gaps.append("Planner: DAG depends_on ausente")
    if not Path("pkf/utils/ast_parser.py").is_file():
        gaps.append("Utils: ast_parser.py ausente")
    if not Path("pkf/utils/impact_graph.py").is_file():
        gaps.append("Utils: impact_graph.py ausente")
    if Path("pkf/web/state_events.py").is_file():
        gaps.append("Web: state_events.py ainda presente (Grupo D removido)")
    return gaps


def run_build_review_cycle(workspace: Path) -> tuple[int, bool, list[str], str]:
    """Simula build+review: regenera spec, verifica lacunas, aprova quando conforme."""
    slug = save_platform_spec(workspace)
    spec_path = workspace / ".pkf" / "specs" / f"{slug}.md"
    spec_text = spec_path.read_text(encoding="utf-8")
    cycles = 0
    gaps: list[str] = []
    for cycle in range(1, MAX_REVIEW_FIX_CYCLES + 1):
        cycles = cycle
        gaps = _implementation_gaps(spec_text)
        if not gaps:
            break
    approved = not gaps
    review = f"""# Review pkf-platform ({slug})

Ciclo {cycles}/{MAX_REVIEW_FIX_CYCLES}. Spec alinhada com menu de contexto, PATCH rename,
confirmacao de exclusao, variaveis CSS, Headroom, 9Router skip 401, tier qualidade, benchmark,
build DAG (bloqueio falha, handoff artifacts, memória lazy, depends_on, run_build_dag), grafo de impacto AST,
get_last_verification, coerencia /spec (save_spec, classificador, arquiteto), auto-scroll e composer largo,
hardening de producao (auth, preview, deploy, remediação auditoria agentes, sem pub/sub Grupo D).

Status: {"APROVADO" if approved else "REPROVADO"}
"""
    if gaps:
        review += "\nPendencias:\n" + "\n".join(f"- {g}" for g in gaps)
    ok, _issues = parse_review_status(review)
    return cycles, ok and approved, gaps, review


def test_platform_build_review_cycle(tmp_path: Path):
    cycles, approved, gaps, review = run_build_review_cycle(tmp_path)
    assert cycles >= 1
    assert approved, gaps
    assert "APROVADO" in review
