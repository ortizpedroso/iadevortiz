from __future__ import annotations

import ast
import json
import math
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from pkf.config import pkf_dir
from pkf.workspace import Workspace

_INDEX_NAME = "semantic.json"
_TOKEN = re.compile(r"[a-z0-9_]+", re.IGNORECASE)
_MODEL: object | None = None
_EMBED_DIM = 384


def _index_path(workspace_root: Path) -> Path:
    return pkf_dir(workspace_root) / "index" / _INDEX_NAME


def _use_test_embedder() -> bool:
    return os.getenv("PKF_TEST_SEMANTIC", "").strip() == "1"


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _test_embed(text: str) -> list[float]:
    vec = [0.0] * _EMBED_DIM
    for token in _tokenize(text):
        vec[hash(token) % _EMBED_DIM] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _get_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    if _use_test_embedder():
        _MODEL = "test"
        return _MODEL
    try:
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    except (ImportError, OSError, RuntimeError):
        _MODEL = "test"
    return _MODEL


def _embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _get_model()
    if model == "test":
        return [_test_embed(t) for t in texts]
    vectors = model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=False))


def _chunk_python(content: str, rel_path: str) -> list[dict]:
    chunks: list[dict] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return _chunk_lines(content, rel_path)
    lines = content.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = max(getattr(node, "lineno", 1) - 1, 0)
            end = getattr(node, "end_lineno", start + 1) or (start + 1)
            snippet = "\n".join(lines[start:end]).strip()
            if not snippet:
                continue
            chunks.append(
                {
                    "id": f"{rel_path}:{node.name}",
                    "path": rel_path,
                    "start_line": start + 1,
                    "text": snippet[:2000],
                }
            )
    return chunks or _chunk_lines(content, rel_path)


def _chunk_lines(content: str, rel_path: str, block_size: int = 80) -> list[dict]:
    lines = content.splitlines()
    chunks: list[dict] = []
    for i in range(0, len(lines), block_size):
        block = "\n".join(lines[i : i + block_size]).strip()
        if not block:
            continue
        chunks.append(
            {
                "id": f"{rel_path}:L{i + 1}",
                "path": rel_path,
                "start_line": i + 1,
                "text": block[:2000],
            }
        )
    return chunks


def chunk_file(content: str, rel_path: str) -> list[dict]:
    if rel_path.endswith(".py"):
        return _chunk_python(content, rel_path)
    return _chunk_lines(content, rel_path)


def _load_index(workspace_root: Path) -> list[dict]:
    path = _index_path(workspace_root)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data.get("chunks", [])


def _save_index(workspace_root: Path, chunks: list[dict]) -> None:
    path = _index_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(UTC).isoformat(),
        "chunks": chunks,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def update_file_index(workspace: Workspace, rel_path: str) -> None:
    rel = rel_path.replace("\\", "/")
    target = workspace.root / rel
    chunks = _load_index(workspace.root)
    chunks = [c for c in chunks if c.get("path") != rel]
    if target.is_file() and not workspace.is_secret(target) and not workspace.is_ignored(target):
        try:
            content = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            content = ""
        if content.strip():
            new_chunks = chunk_file(content, rel)
            texts = [c["text"] for c in new_chunks]
            embeddings = _embed_texts(texts)
            for chunk, embedding in zip(new_chunks, embeddings, strict=False):
                chunk["embedding"] = embedding
            chunks.extend(new_chunks)
    _save_index(workspace.root, chunks)


def rebuild_index(workspace: Workspace, limit: int = 200) -> str:
    chunks: list[dict] = []
    count = 0
    for file_path in workspace.iter_files():
        rel = workspace.rel(file_path)
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        file_chunks = chunk_file(content, rel)
        texts = [c["text"] for c in file_chunks]
        embeddings = _embed_texts(texts)
        for chunk, embedding in zip(file_chunks, embeddings, strict=False):
            chunk["embedding"] = embedding
        chunks.extend(file_chunks)
        count += 1
        if count >= limit:
            break
    _save_index(workspace.root, chunks)
    return f"Índice semântico: {len(chunks)} chunks de {count} arquivos."


def semantic_search(workspace: Workspace, query: str, top_k: int = 5) -> str:
    query = (query or "").strip()
    if not query:
        return "Informe uma query de busca semântica."
    chunks = _load_index(workspace.root)
    if not chunks:
        rebuild_index(workspace)
        chunks = _load_index(workspace.root)
    if not chunks:
        return "Índice semântico vazio."
    query_vec = _embed_texts([query])[0]
    scored: list[tuple[float, dict]] = []
    for chunk in chunks:
        vec = chunk.get("embedding") or []
        score = _cosine(query_vec, vec)
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored:
        return "Nenhum resultado semântico."
    lines: list[str] = []
    for score, chunk in scored[:top_k]:
        lines.append(
            f"{chunk.get('path')}:{chunk.get('start_line', '?')} (score={score:.3f})\n{chunk.get('text', '')[:400]}"
        )
    return "\n\n".join(lines)
