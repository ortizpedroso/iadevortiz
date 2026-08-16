from __future__ import annotations

MAX_BUILD_RETRIES = 2


async def run_brainstorm(router, spec_name: str | None) -> str:
    """Fase rápida de contexto antes do build (estilo MiMo compose)."""
    architect = router.agents.get("architect")
    if not architect:
        return ""
    prompt = (
        "Brainstorm rápido antes do build. Leia project_context e get_spec. "
        "Resuma em até 12 linhas: convenções do repo, arquivos relevantes, "
        "riscos e ordem sugerida de implementação. Não escreva código."
    )
    if spec_name:
        prompt += f"\nSpec ativa: {spec_name}"
    try:
        return await architect.process(prompt)
    except Exception:
        return ""


def verify_ok(verify_text: str) -> bool:
    lower = verify_text.lower()
    if "nenhum arquivo" in lower or "no_build_session" in lower:
        return False
    if "ok" in lower and "falha" not in lower:
        return True
    return "arquivo" in lower or "gerado" in lower
