from pkf.config import fallback_model_on_not_found
from pkf.config import fallback_model_on_not_found as fb


def test_openai_fallback_chain_from_gpt4o_mini():
    base = "https://api.openai.com/v1"
    assert fallback_model_on_not_found("gpt-4o-mini", base) == "gpt-4o"
    assert fb("gpt-4o", base) == "gpt-3.5-turbo"
    assert fb("gpt-3.5-turbo", base) is None


def test_openai_fallback_ignored_for_other_providers():
    assert fallback_model_on_not_found("gpt-4o-mini", "https://api.groq.com/openai/v1") is None
