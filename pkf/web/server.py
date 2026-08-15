from __future__ import annotations

import asyncio
import os
import webbrowser
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pkf.errors import explain_provider_error
from pkf.providers import ping_provider
from pkf.router import Router
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
        healthy, detail = await ping_provider(router.client)
        snapshot = router.snapshot()
        snapshot["provider_ok"] = healthy
        snapshot["preview"] = preview_info(router.workspace)
        if snapshot["preview"].get("entry"):
            snapshot["preview"]["path"] = f"/preview/{snapshot['preview']['entry']}"
        if not healthy:
            snapshot["provider_error"] = explain_provider_error(router.provider_name, Exception(detail))
        return {
            "session": snapshot,
            "messages": app.state.history.messages,
        }

    @app.post("/api/reset")
    async def reset():
        async with app.state.lock:
            router.reset_conversation()
            app.state.history.clear()
        return {"ok": True, "session": router.snapshot()}

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
                    agent = router.cycle.last_agent or "sistema"
                    message = {"role": "assistant", "content": reply or "", "agent": agent}
                    app.state.history.append(message)
                    await websocket.send_json({"type": "done", **message, **router.snapshot()})
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
