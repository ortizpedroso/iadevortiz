from pkf.agents.compact import compact_messages
from pkf.config import compaction_budget


def test_compact_truncates_long_tool_results():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "tool", "content": "x" * 5000},
    ]
    out = compact_messages(messages, "llama-3.1-8b-instant")
    assert len(out[1]["content"]) < 5000


def test_compact_keeps_tool_call_groups():
    messages = [
        {"role": "system", "content": "sys"},
        *[{"role": "user", "content": f"u{i}"} for i in range(15)],
        {"role": "assistant", "content": "", "tool_calls": [{"id": "1", "type": "function"}]},
        {"role": "tool", "content": "result", "tool_call_id": "1"},
    ]
    out = compact_messages(messages)
    roles = [m["role"] for m in out if m["role"] != "system"]
    if "tool" in roles:
        tool_idx = roles.index("tool")
        assert tool_idx > 0


def test_compaction_budget_by_model():
    b = compaction_budget("gemini-2.0-flash")
    assert b["max_messages"] >= 16
