from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PKF_DIR_NAME = ".pkf"
NODE_LIMIT = 12
MAX_TOOL_ROUNDS = int(os.getenv("PKF_MAX_TOOL_ROUNDS", "16"))
MAX_BUILD_TOOL_ROUNDS = int(os.getenv("PKF_BUILD_TOOL_ROUNDS", "30"))
RELEVANCE_THRESHOLD = 2
API_TIMEOUT = 120.0
COMMAND_TIMEOUT = 45
MAX_FILE_BYTES = 200_000
MAX_SEARCH_MATCHES = 40

DEFAULT_IGNORES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".pkf",
    "system_prompts_leaks",
    "Anthropic",
    "OpenAI",
    "Google",
    "xAI",
    "Perplexity",
    "Microsoft",
    "Cursor",
    "Meta",
    "Mistral",
    "Kimi",
    "DeepSeek",
    "GLM",
    "OpenCode",
    "Pi",
    "Notion",
    "Qwen",
    "Misc",
    "assets",
    ".github",
}

SECRET_NAMES = {".env", ".env.local", "credentials.json", "secrets.json"}
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    model: str
    supports_tools: bool = True


def providers() -> dict[str, ProviderConfig]:
    configs = {
        "ollama": ProviderConfig(
            name="ollama",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
            model=os.getenv("OLLAMA_MODEL", "llama3:8b"),
            supports_tools=os.getenv("OLLAMA_TOOLS", "1") == "1",
        ),
        "kimi": ProviderConfig(
            name="kimi",
            base_url=os.getenv("KIMI_BASE_URL", "https://api.moonshot.ai/v1"),
            api_key=os.getenv("MOONSHOT_API_KEY", ""),
            model=os.getenv("KIMI_MODEL", "kimi-k3"),
        ),
        "groq": ProviderConfig(
            name="groq",
            base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            api_key=os.getenv("GROQ_API_KEY", ""),
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        ),
        "gemini": ProviderConfig(
            name="gemini",
            base_url=os.getenv(
                "GEMINI_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta/openai/",
            ),
            api_key=os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", "")),
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        ),
    }
    configs = {k: v for k, v in configs.items() if v.api_key or k in ("ollama",)}
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        configs["openai"] = ProviderConfig(
            name="openai",
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            api_key=openai_key,
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        )
    return configs


def default_provider() -> str:
    explicit = os.getenv("PKF_PROVIDER", "").strip()
    if explicit:
        return explicit
    if os.getenv("PKF_ENV") == "production":
        if os.getenv("GROQ_API_KEY"):
            return "groq"
        if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
            return "gemini"
        if os.getenv("MOONSHOT_API_KEY"):
            return "kimi"
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
    return "ollama"


def default_fallback(provider_name: str) -> str | None:
    explicit = os.getenv("PKF_FALLBACK", "").strip()
    if explicit:
        return explicit or None
    if os.getenv("PKF_ENV") == "production":
        return None
    if provider_name == "kimi":
        return "ollama"
    if provider_name == "openai":
        return "ollama"
    return None


def auth_token() -> str:
    return os.getenv("PKF_AUTH_TOKEN", "").strip()


def ui_host() -> str:
    return os.getenv("PKF_HOST", "127.0.0.1")


def ui_port() -> int:
    return int(os.getenv("PKF_PORT", "8765"))


def model_for_task(task: str, default: str) -> str:
    """Modelo por fase: PKF_BUILD_MODEL, PKF_SPEC_MODEL, etc."""
    key = f"PKF_{task.upper()}_MODEL"
    return os.getenv(key, "").strip() or default


def tool_rounds_for_agent(agent_name: str) -> int:
    if agent_name in {"frontend", "backend", "logic", "tester"}:
        return MAX_BUILD_TOOL_ROUNDS
    return MAX_TOOL_ROUNDS


def pkf_dir(workspace: Path) -> Path:
    path = workspace / PKF_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    (path / "specs").mkdir(exist_ok=True)
    (path / "reviews").mkdir(exist_ok=True)
    (path / "memory").mkdir(exist_ok=True)
    return path
