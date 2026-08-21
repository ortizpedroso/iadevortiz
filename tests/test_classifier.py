from pkf.agents.base import parse_text_tool_calls
from pkf.classifier import classify_intent
from pkf.workflow.cycle import DevCycle, parse_command


def test_review_overrides_domain_keyword():
    intent = classify_intent("revise o backend da api")
    assert intent.agent == "reviewer"
    assert intent.kind == "review_request"


def test_frontend_keyword():
    intent = classify_intent("crie um botão em React")
    assert intent.agent == "frontend"
    assert intent.kind == "feature"


def test_conversational_question_not_feature():
    intent = classify_intent("você consegue criar um sistema sozinho")
    assert intent.kind == "question"
    assert intent.agent == "generalista"


def test_detailed_feature_request_still_routes_to_architect():
    intent = classify_intent("crie um sistema de gestão de estoque com controle de validade")
    assert intent.kind == "feature"
    assert intent.agent == "architect"


def test_review_command_routes_to_reviewer():
    intent = classify_intent("/review", last_agent="backend")
    assert intent.agent == "reviewer"
    assert intent.kind == "command"


def test_build_after_spec_routes_to_frontend():
    intent = classify_intent("/build", last_agent="architect")
    assert intent.agent == "frontend"
    assert intent.kind == "command"


def test_parse_spec_command():
    command, rest = parse_command("/spec login oauth")
    assert command == "/spec"
    assert rest == "login oauth"


def test_cycle_feature_starts_spec():
    cycle = DevCycle()
    phase, payload = cycle.apply(None, "feature", "tela de login")
    assert phase == "SPEC"
    assert "save_spec" in payload


def test_cycle_change_updates_spec():
    cycle = DevCycle(phase="BUILD", active_spec="login")
    phase, payload = cycle.apply(None, "change", "adicione oauth")
    assert phase == "SPEC"
    assert cycle.spec_status == "pending_approval"
    assert "ATUALIZE" in payload


def test_parse_function_tool_call():
    text = '<function=list_dir>{"path": "."}</function>'
    calls = parse_text_tool_calls(text)
    assert calls[0]["name"] == "list_dir"
    assert calls[0]["arguments"]["path"] == "."
