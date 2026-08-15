from pathlib import Path

from pkf.web.history import ChatHistory


def test_chat_history_roundtrip(tmp_path: Path):
    log = ChatHistory(tmp_path)
    log.append({"role": "user", "content": "olá"})
    again = ChatHistory(tmp_path)
    assert again.messages[0]["content"] == "olá"
    again.clear()
    assert ChatHistory(tmp_path).messages == []
