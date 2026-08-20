from __future__ import annotations

import asyncio
import os
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import APIConnectionError, APIStatusError, APITimeoutError

from pkf import __version__
from pkf.config import auth_token
from pkf.db.config import database_enabled
from pkf.db.engine import close_db, init_db
from pkf.errors import explain_provider_error
from pkf.ninerouter import ninerouter_enabled, ninerouter_health
from pkf.providers import ping_provider
from pkf.router import Router
from pkf.spec.store import approve_spec, update_spec_stack
from pkf.web.auth import (
    AuthMiddleware,
    SecurityHeadersMiddleware,
    _extract_token,
    check_ws_auth,
)
from pkf.web.history import ChatHistory
from pkf.web.library import (
    activate_chat,
    activate_project,
    attach_chat,
    create_chat,
    delete_chat,
    delete_project,
    delete_projects_bulk,
    library_snapshot,
    pin_project,
)
from pkf.web.preview import preview_info, redirect_preview_entry, serve_preview_file
from pkf.web_search import web_search_configured
from pkf.workflow.cycle import DevCycle
from pkf.workflow.tasks import TaskTracker
from pkf.workspace_index import build_file_tree, list_changes

PKG_DIR = Path(__file__).resolve().parent
LEGACY_STATIC = PKG_DIR / "static"


async def build_session_snapshot(router: Router, history: ChatHistory) -> dict:
    """Snapshot consistente entre HTTP e WebSocket (DB tasks/cycle têm prioridade)."""
    snapshot = router.snapshot()
    if database_enabled():
        await history.db_context.setup()
        snapshot["tasks"] = await history.db_context.load_tasks()
        cycle = await history.db_context.load_dev_cycle()
        if cycle:
            snapshot["phase"] = cycle.phase
            snapshot["active_spec"] = cycle.active_spec
            snapshot["spec_status"] = cycle.spec_status
            snapshot["goal"] = cycle.goal
            snapshot["last_agent"] = cycle.last_agent or snapshot.get("last_agent")
    return snapshot


def _frontend_dist_candidates() -> list[Path]:
    roots = []
    if app_root := os.getenv("PKF_APP_ROOT", "").strip():
        roots.append(Path(app_root))
    roots.append(Path(__file__).resolve().parents[2])
    roots.append(Path("/app"))
    seen: set[str] = set()
    candidates: list[Path] = []
    for root in roots:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(root / "frontend" / "dist")
    return candidates


def _static_root() -> Path:
    for dist in _frontend_dist_candidates():
        if dist.is_dir() and (dist / "index.html").exists():
            return dist
    return LEGACY_STATIC


def create_app(router: Router) -> FastAPI:
    static_root = _static_root()
    use_vite = static_root != LEGACY_STATIC

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if database_enabled():
            await init_db()
        history: ChatHistory = app.state.history
        await history.load()
        if database_enabled():
            router.db = history.db_context
            cycle = await history.db_context.load_dev_cycle()
            if cycle:
                router.cycle = cycle
        yield
        if database_enabled():
            await close_db()

    app = FastAPI(title="PKF", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AuthMiddleware)
    app.state.router = router
    app.state.history = ChatHistory(router.workspace.root, router.workspace)
    app.state.lock = asyncio.Lock()

    if use_vite:
        assets_dir = static_root / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    else:
        app.mount("/assets", StaticFiles(directory=LEGACY_STATIC), name="assets")

    @app.get("/")
    async def index():
        return FileResponse(static_root / "index.html")

    @app.get("/api/health")
    async def health(request: Request):
        token = _extract_token(request)
        authed = not auth_token() or token == auth_token()
        payload = {
            "ok": True,
            "auth_required": bool(auth_token()),
            "database": database_enabled(),
            "ui": "vite" if use_vite else "legacy",
            "version": __version__,
            "git_sha": os.getenv("PKF_GIT_SHA", "").strip() or None,
        }
        if authed:
            payload["web_search"] = web_search_configured()
            payload["ninerouter"] = ninerouter_enabled()
            payload["provider_router"] = app.state.router.pool.status()
            if ninerouter_enabled():
                ok, detail = ninerouter_health()
                payload["ninerouter_ok"] = ok
                if not ok:
                    payload["ninerouter_error"] = detail
        return payload

    @app.get("/api/preview")
    async def preview_api():
        info = preview_info(router.workspace)
        if info["entry"]:
            info["path"] = f"/preview/{info['entry']}"
        return info

    @app.get("/preview")
    async def preview_root(request: Request):
        token = _extract_token(request)
        return redirect_preview_entry(router.workspace, token)

    @app.get("/preview/{rel_path:path}")
    async def preview_file(rel_path: str):
        return serve_preview_file(router.workspace, rel_path)

    @app.get("/api/library")
    async def library():
        history: ChatHistory = app.state.history
        data = await library_snapshot(router.workspace, history.db_context)
        if router.workspace.project:
            for project in data.get("projects", []):
                project["is_active"] = project.get("slug") == router.workspace.project
        return data

    @app.post("/api/chats")
    async def chats_create():
        history: ChatHistory = app.state.history
        async with app.state.lock:
            result = await create_chat(router.workspace, history.db_context)
            router.cycle = DevCycle()
            router.cycle.persist(router.workspace.root)
            history.messages = []
            history.active_chat_id = result.get("chat_id")
            for agent in router.agents.values():
                if agent.messages:
                    agent.messages = [agent.messages[0]]
        snapshot = router.snapshot()
        return {
            "ok": True,
            **result,
            "session": snapshot,
            "library": await library_snapshot(router.workspace, history.db_context),
        }

    @app.post("/api/chats/{chat_id}/activate")
    async def chats_activate(chat_id: str):
        history: ChatHistory = app.state.history
        async with app.state.lock:
            messages = await activate_chat(router.workspace, chat_id, history.db_context)
            history.active_chat_id = chat_id
            await history.replace_messages(messages)
            router.cycle = DevCycle.load(router.workspace.root)
            if database_enabled():
                cycle = await history.db_context.load_dev_cycle()
                if cycle:
                    router.cycle = cycle
            router._register_core_agents()
            router.restore_chat_history(history.messages)
        snapshot = router.snapshot()
        if database_enabled():
            await history.db_context.setup()
            snapshot["tasks"] = await history.db_context.load_tasks()
        return {"ok": True, "session": snapshot, "messages": history.messages}

    @app.delete("/api/chats/{chat_id}")
    async def chats_delete(chat_id: str):
        history: ChatHistory = app.state.history
        try:
            async with app.state.lock:
                await delete_chat(router.workspace, chat_id, history.db_context)
                if database_enabled():
                    await history.db_context.refresh_active_session()
                    history.active_chat_id = (
                        str(history.db_context.session_id) if history.db_context.session_id else None
                    )
                    history.messages = await history.db_context.get_messages()
                    router.cycle = await history.db_context.load_dev_cycle() or DevCycle()
                else:
                    from pkf.web.library import load_file_messages

                    history.active_chat_id, history.messages = load_file_messages(router.workspace.global_root)
                    router.cycle = DevCycle.load(router.workspace.root)
                router._register_core_agents()
                router.restore_chat_history(history.messages)
        except ValueError as exc:
            return JSONResponse(status_code=404, content={"ok": False, "error": str(exc)})
        return {
            "ok": True,
            "library": await library_snapshot(router.workspace, history.db_context),
            "session": router.snapshot(),
            "messages": history.messages,
        }

    @app.post("/api/chats/{chat_id}/attach")
    async def chats_attach(chat_id: str, payload: dict | None = None):
        payload = payload or {}
        history: ChatHistory = app.state.history
        slug = payload.get("project_slug") or payload.get("slug")
        async with app.state.lock:
            await attach_chat(
                router.workspace,
                chat_id,
                slug,
                history.db_context,
                history.active_chat_id,
            )
            if history.active_chat_id == chat_id:
                router.cycle = DevCycle.load(router.workspace.root)
                if database_enabled():
                    cycle = await history.db_context.load_dev_cycle()
                    if cycle:
                        router.cycle = cycle
                router._register_core_agents()
        return {"ok": True, "library": await library_snapshot(router.workspace, history.db_context)}

    @app.post("/api/projects/{slug}/activate")
    async def projects_activate(slug: str):
        history: ChatHistory = app.state.history
        async with app.state.lock:
            await activate_project(router.workspace, slug, history.db_context)
            router.cycle = DevCycle.load(router.workspace.root)
            if database_enabled():
                cycle = await history.db_context.load_dev_cycle()
                if cycle:
                    router.cycle = cycle
            router._register_core_agents()
        return {"ok": True, "session": router.snapshot(), "library": await library_snapshot(router.workspace, history.db_context)}

    @app.patch("/api/projects/{slug}")
    async def projects_rename(slug: str, payload: dict | None = None):
        payload = payload or {}
        history: ChatHistory = app.state.history
        name = (payload.get("name") or "").strip()
        if not name:
            return JSONResponse({"ok": False, "error": "Nome inválido"}, status_code=400)
        try:
            async with app.state.lock:
                from pkf.web.library import rename_project

                await rename_project(router.workspace, slug, name, history.db_context)
        except ValueError as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
        return {
            "ok": True,
            "library": await library_snapshot(router.workspace, history.db_context),
            "session": router.snapshot(),
        }

    @app.delete("/api/projects/{slug}")
    async def projects_delete(slug: str):
        history: ChatHistory = app.state.history
        async with app.state.lock:
            await delete_project(router.workspace, slug, history.db_context)
            router.cycle = DevCycle.load(router.workspace.root)
            router._register_core_agents()
        return {"ok": True, "library": await library_snapshot(router.workspace, history.db_context)}

    @app.post("/api/projects/bulk-delete")
    async def projects_bulk_delete(payload: dict | None = None):
        payload = payload or {}
        history: ChatHistory = app.state.history
        delete_all = bool(payload.get("all"))
        slugs = payload.get("slugs") if isinstance(payload.get("slugs"), list) else []
        if not delete_all and not slugs:
            return JSONResponse({"ok": False, "error": "Informe slugs ou all=true"}, status_code=400)
        async with app.state.lock:
            result = await delete_projects_bulk(
                router.workspace,
                slugs=[str(s) for s in slugs],
                delete_all=delete_all,
                db=history.db_context,
            )
            router.cycle = DevCycle.load(router.workspace.root)
            router._register_core_agents()
        library = await library_snapshot(router.workspace, history.db_context)
        ok = not result["failed"]
        return {
            "ok": ok,
            "deleted": result["deleted"],
            "failed": result["failed"],
            "library": library,
            "session": router.snapshot(),
        }

    @app.post("/api/projects/{slug}/pin")
    async def projects_pin(slug: str, payload: dict | None = None):
        payload = payload or {}
        pinned = bool(payload.get("pinned"))
        history: ChatHistory = app.state.history
        try:
            await pin_project(router.workspace, slug, pinned)
        except ValueError as exc:
            return JSONResponse(status_code=404, content={"ok": False, "error": str(exc)})
        return {"ok": True, "library": await library_snapshot(router.workspace, history.db_context)}

    @app.get("/api/session")
    async def session():
        history: ChatHistory = app.state.history
        try:
            healthy, detail = await ping_provider(router.client)
            snapshot = await build_session_snapshot(router, history)
            snapshot["provider_ok"] = healthy
            snapshot["database"] = database_enabled()
            project_preview = snapshot.get("project_preview") or preview_info(router.workspace)
            snapshot["project_preview"] = project_preview
            if project_preview.get("entry"):
                snapshot["project_preview"]["path"] = f"/preview/{project_preview['entry']}"
            if not healthy:
                snapshot["provider_error"] = explain_provider_error(
                    router.provider_name, Exception(detail)
                )
            return {"session": snapshot, "messages": history.messages, "library": await library_snapshot(router.workspace, history.db_context)}
        except (OSError, RuntimeError, ValueError, TypeError, APIConnectionError, APIStatusError, APITimeoutError) as exc:
            return {
                "session": {
                    "provider_ok": False,
                    "provider_error": explain_provider_error(router.provider_name, exc),
                    "project_preview": {"available": False},
                    "database": database_enabled(),
                },
                "messages": history.messages,
            }

    @app.post("/api/reset")
    async def reset():
        history: ChatHistory = app.state.history
        async with app.state.lock:
            router.reset_conversation()
            await history.clear()
        return {"ok": True, "session": router.snapshot()}

    @app.post("/api/spec/approve")
    async def spec_approve(payload: dict | None = None):
        payload = payload or {}
        name = payload.get("name") or router.cycle.active_spec
        if not name:
            return {"ok": False, "error": "Nenhuma spec ativa"}
        confirmed = payload.get("confirmed_stack") or {}
        doc = approve_spec(router.workspace.root, name, confirmed)
        router.cycle = DevCycle.load(router.workspace.root)
        router.cycle.spec_status = "approved"
        router.cycle.persist(router.workspace.root)
        history: ChatHistory = app.state.history
        if database_enabled():
            await history.db_context.setup()
            await history.db_context.persist_cycle(router.cycle)
        preview = doc.to_preview_dict()
        preview["name"] = name
        return {"ok": True, "spec": preview, "session": router.snapshot()}

    @app.get("/api/files")
    async def files_tree():
        return {"tree": build_file_tree(router.workspace)}

    @app.get("/api/changes")
    async def recent_changes():
        history: ChatHistory = app.state.history
        if database_enabled():
            await history.db_context.setup()
            changes = await history.db_context.list_changes()
            if changes:
                return {"changes": changes}
        return {"changes": list_changes(router.workspace)}

    @app.get("/api/tasks")
    async def task_tree():
        history: ChatHistory = app.state.history
        if database_enabled():
            await history.db_context.setup()
            return {"tasks": await history.db_context.load_tasks()}
        return {"tasks": TaskTracker(router.workspace.root).to_list()}

    @app.post("/api/spec/stack")
    async def spec_stack(payload: dict | None = None):
        payload = payload or {}
        name = payload.get("name") or router.cycle.active_spec
        if not name:
            return {"ok": False, "error": "Nenhuma spec ativa"}
        confirmed = payload.get("confirmed_stack") or {}
        doc = update_spec_stack(router.workspace.root, name, confirmed)
        preview = doc.to_preview_dict()
        preview["name"] = name
        return {"ok": True, "spec": preview}

    @app.websocket("/ws")
    async def chat_socket(websocket: WebSocket):
        if not check_ws_auth(websocket):
            await websocket.close(code=4401, reason="Token inválido")
            return
        await websocket.accept()
        history: ChatHistory = app.state.history
        await history.load()
        await websocket.send_json({"type": "session", **await build_session_snapshot(router, history)})

        async def on_event(event: dict) -> None:
            await websocket.send_json(event)

        router.set_event_handler(on_event)
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") != "message":
                    continue
                content = (data.get("content") or "").strip()
                if not content:
                    continue
                if app.state.lock.locked():
                    await websocket.send_json(
                        {"type": "error", "content": "Aguarde a resposta anterior terminar."}
                    )
                    continue
                async with app.state.lock:
                    await history.append({"role": "user", "content": content})
                    try:
                        reply = await router.handle(content)
                    except Exception as exc:  # noqa: BLE001 — surface any agent/provider failure to the client
                        await websocket.send_json(
                            {
                                "type": "error",
                                "content": explain_provider_error(router.provider_name, exc),
                            }
                        )
                        continue
                    agent = "pkf" if router.ui_mode else (router.cycle.last_agent or "sistema")
                    message = {"role": "assistant", "content": reply or "", "agent": agent}
                    await history.append(message)
                    if database_enabled():
                        await history.db_context.persist_cycle(router.cycle)
                    payload = {"type": "done", **message, **router.snapshot()}
                    await websocket.send_json(payload)
        except WebSocketDisconnect:
            pass
        finally:
            router.set_event_handler(None)

    return app


def run_ui(router: Router, host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn

    app = create_app(router)
    url = f"http://{host}:{port}" if host != "0.0.0.0" else f"http://127.0.0.1:{port}"
    ui_mode = "Vite" if _static_root() != LEGACY_STATIC else "legacy"
    print(f"PKF UI ({ui_mode}) em {url}")
    if database_enabled():
        print("PostgreSQL: ativo")
    if host in {"127.0.0.1", "localhost"} and os.getenv("PKF_NO_BROWSER") != "1":
        webbrowser.open(url)
    uvicorn.run(app, host=host, port=port, log_level="info")
