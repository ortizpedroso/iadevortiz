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
MAX_REVIEW_FIX_CYCLES = int(os.getenv("PKF_REVIEW_FIX_CYCLES", "3"))
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
    from pkf.ninerouter import (
        ninerouter_api_key,
        ninerouter_chat_base_url,
        ninerouter_chat_model,
        ninerouter_enabled,
    )

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
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        ),
        "mimo": ProviderConfig(
            name="mimo",
            base_url=os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1"),
            api_key=os.getenv("MIMO_API_KEY", ""),
            model=os.getenv("MIMO_MODEL", "mimo-v2-flash"),
        ),
        "deepseek": ProviderConfig(
            name="deepseek",
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            supports_tools=os.getenv("DEEPSEEK_TOOLS", "0") == "1",
        ),
    }
    configs = {k: v for k, v in configs.items() if v.api_key or k == "ollama"}
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        configs["openai"] = ProviderConfig(
            name="openai",
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            api_key=openai_key,
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        )
    if ninerouter_enabled():
        configs["ninerouter"] = ProviderConfig(
            name="ninerouter",
            base_url=ninerouter_chat_base_url(),
            api_key=ninerouter_api_key(),
            model=ninerouter_chat_model(),
        )
    return configs


def default_provider() -> str:
    from pkf.ninerouter import ninerouter_enabled, ninerouter_should_skip

    explicit = os.getenv("PKF_PROVIDER", "").strip().lower()
    if explicit in {"9router", "9-router"}:
        return "ninerouter"
    if explicit:
        return explicit
    if ninerouter_enabled():
        skip, _reason = ninerouter_should_skip()
        if not skip:
            return "ninerouter"
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    if os.getenv("MOONSHOT_API_KEY"):
        return "kimi"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("DEEPSEEK_API_KEY"):
        return "deepseek"
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


def headroom_proxy_url() -> str | None:
    """URL do proxy Headroom (OpenAI-compatible). Opt-in via PKF_HEADROOM_PROXY_URL."""
    url = os.getenv("PKF_HEADROOM_PROXY_URL", "").strip()
    return url or None


QUALITY_TIER_AGENTS = frozenset({"architect", "reviewer"})


def quality_tier_provider() -> str | None:
    """Provedor do tier de qualidade (ex.: ninerouter com kr/claude-*)."""
    name = os.getenv("PKF_TIER_QUALITY", "").strip().lower()
    if name in {"9router", "9-router"}:
        return "ninerouter"
    return name or None


def quality_tier_model() -> str | None:
    explicit = os.getenv("PKF_QUALITY_MODEL", "").strip()
    return explicit or None


def agent_uses_quality_tier(agent: str) -> bool:
    return agent in QUALITY_TIER_AGENTS and quality_tier_provider() is not None


def agent_provider_override(agent: str) -> str | None:
    """Provider dedicado por agente — ex.: PKF_BACKEND_PROVIDER=groq"""
    key = f"PKF_{agent.upper()}_PROVIDER"
    explicit = os.getenv(key, "").strip().lower()
    if explicit in {"9router", "9-router"}:
        return "ninerouter"
    return explicit or None


def model_for_task(task: str, default: str) -> str:
    """Modelo por fase: PKF_BUILD_MODEL, PKF_ARCHITECT_MODEL, PKF_REASONING_MODEL, etc."""
    key = f"PKF_{task.upper()}_MODEL"
    explicit = os.getenv(key, "").strip()
    if explicit:
        return explicit
    from pkf.deepseek import deepseek_enabled, reasoner_model
    from pkf.reasoning import reasoning_agents

    if task in reasoning_agents() and deepseek_enabled():
        reasoning = os.getenv("PKF_REASONING_MODEL", "").strip() or reasoner_model()
        if reasoning:
            return reasoning
    return default


def tool_rounds_for_agent(agent_name: str) -> int:
    if agent_name in {"frontend", "backend", "logic", "tester"}:
        return MAX_BUILD_TOOL_ROUNDS
    return MAX_TOOL_ROUNDS


GROQ_FALLBACK_MODEL = os.getenv("PKF_GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")

_GROQ_HEAVY_MODELS = {
    "llama-3.3-70b-versatile",
    "qwen-2.5-coder-32b",
    "qwen-qwq-32b",
    "mixtral-8x7b-32768",
}


def is_groq_client(base_url: str) -> bool:
    return "groq.com" in (base_url or "").lower()


def is_openai_client(base_url: str) -> bool:
    return "api.openai.com" in (base_url or "").lower()


def is_gemini_client(base_url: str) -> bool:
    url = (base_url or "").lower()
    return "generativelanguage.googleapis.com" in url or "googleapis.com" in url


OPENAI_FALLBACK_MODELS: tuple[str, ...] = tuple(
    part.strip()
    for part in os.getenv("PKF_OPENAI_FALLBACK_MODELS", "gpt-4o,gpt-3.5-turbo").split(",")
    if part.strip()
)

_OPENAI_MODEL_CHAIN: tuple[str, ...] = ("gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo")

GEMINI_FALLBACK_MODELS: tuple[str, ...] = tuple(
    part.strip()
    for part in os.getenv("PKF_GEMINI_FALLBACK_MODELS", "gemini-3.6-flash,gemini-3.5-flash-lite").split(",")
    if part.strip()
)

_GEMINI_MODEL_CHAIN: tuple[str, ...] = ("gemini-2.5-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite")


def fallback_model_on_rate_limit(current_model: str, base_url: str = "") -> str | None:
    if not is_groq_client(base_url):
        return None
    if current_model in _GROQ_HEAVY_MODELS:
        return GROQ_FALLBACK_MODEL
    return None


def fallback_model_on_not_found(current_model: str, base_url: str = "") -> str | None:
    if is_openai_client(base_url):
        chain = list(_OPENAI_MODEL_CHAIN)
        for model in OPENAI_FALLBACK_MODELS:
            if model not in chain:
                chain.append(model)
    elif is_gemini_client(base_url):
        chain = list(_GEMINI_MODEL_CHAIN)
        for model in GEMINI_FALLBACK_MODELS:
            if model not in chain:
                chain.append(model)
    else:
        return None
    try:
        index = chain.index(current_model)
    except ValueError:
        return chain[0] if chain else None
    if index + 1 < len(chain):
        return chain[index + 1]
    return None


def provider_pool_names() -> list[str]:
    """Ordem de provedores para rotação automática (grátis / nuvem)."""
    from pkf.ninerouter import ninerouter_enabled, ninerouter_should_skip

    available = providers()
    if explicit := os.getenv("PKF_PROVIDER_POOL", "").strip():
        candidates = [p.strip() for p in explicit.split(",") if p.strip()]
    elif ninerouter_enabled():
        skip, _reason = ninerouter_should_skip()
        candidates = (
            ["groq", "gemini", "deepseek", "mimo", "kimi", "openai"]
            if skip
            else ["ninerouter", "groq", "gemini", "deepseek", "mimo", "kimi", "openai"]
        )
    else:
        candidates = ["groq", "gemini", "deepseek", "mimo", "kimi", "openai"]

    if not ninerouter_enabled() or ninerouter_should_skip()[0]:
        candidates = [name for name in candidates if name != "ninerouter"]

    primary = os.getenv("PKF_PROVIDER", "").strip()
    explicit_pool = os.getenv("PKF_PROVIDER_POOL", "").strip()
    if primary and primary not in candidates:
        candidates.insert(0, primary)

    seen_urls: set[str] = set()
    ordered: list[str] = []
    for name in candidates:
        cfg = available.get(name)
        if not cfg or name == "ollama":
            continue
        if not cfg.api_key and name != "ninerouter":
            continue
        url = cfg.base_url.rstrip("/").lower()
        if url in seen_urls:
            continue
        seen_urls.add(url)
        ordered.append(name)

    if primary and primary in ordered and not explicit_pool:
        ordered = [primary] + [n for n in ordered if n != primary]
    return ordered


def rate_limit_cooldown_seconds(exc: Exception) -> int:
    from openai import APIStatusError

    if isinstance(exc, APIStatusError) and exc.response is not None:
        retry_after = exc.response.headers.get("retry-after")
        if retry_after:
            try:
                return max(int(float(retry_after)), 30)
            except ValueError:
                pass
    text = str(exc).lower()
    if "429" not in text and "rate limit" not in text:
        return 0
    if "tokens per day" in text or "tpd" in text:
        return 3600
    return 120


def pkf_dir(workspace: Path) -> Path:
    path = workspace / PKF_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    (path / "specs").mkdir(exist_ok=True)
    (path / "reviews").mkdir(exist_ok=True)
    (path / "memory").mkdir(exist_ok=True)
    (path / "tasks").mkdir(exist_ok=True)
    return path


COMPACTION_BUDGETS: dict[str, dict[str, int]] = {
    "default": {"max_messages": 16, "tool_chars": 3000, "keep_recent": 8},
    "llama-3.1-8b-instant": {"max_messages": 12, "tool_chars": 2500, "keep_recent": 6},
    "llama-3.3-70b": {"max_messages": 14, "tool_chars": 2800, "keep_recent": 7},
    "gemini-2.0-flash": {"max_messages": 20, "tool_chars": 4000, "keep_recent": 10},
    "gemini-2.5-flash": {"max_messages": 20, "tool_chars": 4000, "keep_recent": 10},
    "gemini-3.6-flash": {"max_messages": 20, "tool_chars": 4000, "keep_recent": 10},
    "mimo": {"max_messages": 18, "tool_chars": 3500, "keep_recent": 8},
    "deepseek-reasoner": {"max_messages": 12, "tool_chars": 2500, "keep_recent": 6},
    "deepseek-r1": {"max_messages": 12, "tool_chars": 2500, "keep_recent": 6},
}


def compaction_budget(model: str) -> dict[str, int]:
    model_l = (model or "").lower()
    for key, budget in COMPACTION_BUDGETS.items():
        if key != "default" and key in model_l:
            return budget
    return COMPACTION_BUDGETS["default"]


def judge_model_for(provider_model: str) -> str:
    explicit = os.getenv("PKF_JUDGE_MODEL", "").strip()
    if explicit:
        return explicit
    if "8b" in provider_model.lower() or "instant" in provider_model.lower():
        return provider_model
    return os.getenv("PKF_GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")
