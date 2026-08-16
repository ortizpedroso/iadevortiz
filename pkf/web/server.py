from __future__ import annotations

import asyncio
import os
import webbrowser
from pathlib import Path

from fastapi import Body, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pkf.errors import explain_provider_error
from pkf.providers import ping_provider
from pkf.router import Router
from pkf.spec.store import active_spec_preview, approve_spec, update_spec_stack
from pkf.workflow.cycle import DevCycle
from pkf.workspace_index import build_file_tree, list_changes
from pkf.web.auth import AuthMiddleware, check_ws_auth, _extract_token
from pkf.web.history import ChatHistory
from pkf.web.preview import find_preview_entry, preview_info, redirect_preview_entry, serve_preview_file

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(router: Router) -> FastAPI:
    app = FastAPI(title="PKF", docs_url=None, redoc_url=None)
    app.add_middleware(AuthMiddleware)
    app.state.router = router
    app.state.history = ChatHistory(router.workspace.root)
    app.state.lock = asyncio.Lock()

    app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")

    @app.get("/")
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    async def health():
        return {"ok": True, "auth_required": bool(os.getenv("PKF_AUTH_TOKEN"))}

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

    @app.get("/api/session")
    async def session():
        try:
            healthy, detail = await ping_provider(router.client)
            snapshot = router.snapshot()
            snapshot["provider_ok"] = healthy
            project_preview = snapshot.get("project_preview") or preview_info(router.workspace)
            snapshot["project_preview"] = project_preview
            if project_preview.get("entry"):
                snapshot["project_preview"]["path"] = f"/preview/{project_preview['entry']}"
            if not healthy:
                snapshot["provider_error"] = explain_provider_error(
                    router.provider_name, Exception(detail)
                )
            return {
                "session": snapshot,
                "messages": app.state.history.messages,
            }
        except Exception as exc:
            return {
                "session": {
                    "provider_ok": False,
                    "provider_error": explain_provider_error(router.provider_name, exc),
                    "project_preview": {"available": False},
                },
                "messages": app.state.history.messages,
            }

    @app.post("/api/reset")
    async def reset():
        async with app.state.lock:
            router.reset_conversation()
            app.state.history.clear()
        return {"ok": True, "session": router.snapshot()}

    @app.post("/api/spec/approve")
    async def spec_approve(payload: dict = Body(default_factory=dict)):
        name = payload.get("name") or router.cycle.active_spec
        if not name:
            return {"ok": False, "error": "Nenhuma spec ativa"}
        confirmed = payload.get("confirmed_stack") or {}
        doc = approve_spec(router.workspace.root, name, confirmed)
        router.cycle = DevCycle.load(router.workspace.root)
        router.cycle.spec_status = "approved"
        router.cycle.persist(router.workspace.root)
        preview = doc.to_preview_dict()
        preview["name"] = name
        return {"ok": True, "spec": preview, "session": router.snapshot()}

    @app.get("/api/files")
    async def files_tree():
        return {"tree": build_file_tree(router.workspace)}

    @app.get("/api/changes")
    async def recent_changes():
        return {"changes": list_changes(router.workspace)}

    @app.get("/api/tasks")
    async def task_tree():
        from pkf.workflow.tasks import TaskTracker

        return {"tasks": TaskTracker(router.workspace.root).to_list()}

    @app.post("/api/spec/stack")
    async def spec_stack(payload: dict = Body(default_factory=dict)):
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
        await websocket.send_json({"type": "session", **router.snapshot()})

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
                    app.state.history.append({"role": "user", "content": content})
                    try:
                        reply = await router.handle(content)
                    except Exception as exc:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "content": explain_provider_error(router.provider_name, exc),
                            }
                        )
                        continue
                    agent = "pkf" if router.ui_mode else (router.cycle.last_agent or "sistema")
                    message = {"role": "assistant", "content": reply or "", "agent": agent}
                    app.state.history.append(message)
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
    print(f"PKF UI em {url}")
    if host in {"127.0.0.1", "localhost"} and os.getenv("PKF_NO_BROWSER") != "1":
        webbrowser.open(url)
    uvicorn.run(app, host=host, port=port, log_level="info")
