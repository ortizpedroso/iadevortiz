from pkf.memory.persistent import (
    ensure_memory_files,
    read_memory_context,
    write_checkpoint,
)


def test_memory_files_and_checkpoint(tmp_path):
    ensure_memory_files(tmp_path)
    write_checkpoint(tmp_path, "BUILD", "demo", "teste")
    ctx = read_memory_context(tmp_path)
    assert "Checkpoint" in ctx or "Memória" in ctx
