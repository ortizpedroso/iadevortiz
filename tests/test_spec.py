from pkf.spec.document import SpecDocument, parse_spec, render_spec


def test_parse_spec_with_frontmatter():
    md = """---
{
  "title": "Cardápio",
  "status": "pending_approval",
  "suggested_stack": {"frontend": "HTML/CSS", "backend": "FastAPI"},
  "confirmed_stack": {}
}
---

# Contexto
Um cardápio digital.
"""
    doc = parse_spec(md)
    assert doc.title == "Cardápio"
    assert doc.status == "pending_approval"
    assert doc.suggested_stack["backend"] == "FastAPI"
    assert "cardápio" in doc.body.lower()


def test_render_spec_roundtrip():
    md = render_spec(
        title="Login",
        context="Tela de login",
        requirements="- Email\n- Senha",
        suggested_stack={"frontend": "React", "backend": "FastAPI"},
    )
    doc = parse_spec(md)
    assert doc.status == "pending_approval"
    assert doc.suggested_stack["frontend"] == "React"


def test_effective_stack_prefers_confirmed():
    doc = SpecDocument(
        title="X",
        suggested_stack={"frontend": "HTML"},
        confirmed_stack={"frontend": "React"},
    )
    assert doc.effective_stack["frontend"] == "React"
