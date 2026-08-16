from pkf.spec.updater import save_platform_spec


def test_save_platform_spec(tmp_path):
    slug = save_platform_spec(tmp_path)
    assert slug == "pkf-platform"
    spec_path = tmp_path / ".pkf" / "specs" / "pkf-platform.md"
    assert spec_path.exists()
    text = spec_path.read_text(encoding="utf-8")
    assert "Compactação de contexto" in text or "pipeline compose" in text
    assert "BM25" in text or "MiMo" in text
