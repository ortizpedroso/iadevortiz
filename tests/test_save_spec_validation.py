from pathlib import Path

from pkf.tools.impl import save_spec
from pkf.workspace import Workspace


def _workspace(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path)


def _valid_spec_md() -> str:
    return """---
{
  "title": "Cardápio Digital Whitelabel",
  "status": "pending_approval",
  "suggested_stack": {
    "frontend": "Tailwind CSS",
    "backend": "PHP OO",
    "database": "MySQL",
    "deploy": "Docker Compose"
  },
  "confirmed_stack": {}
}
---

# Contexto
Cardápio digital para restaurantes com vitrine pública, painel administrativo e gestão de pedidos.
O sistema deve suportar múltiplos estabelecimentos em modelo whitelabel.

# Requisitos
- Vitrine pública com categorias e busca
- Painel admin para cardápio, preços e disponibilidade
- Fluxo de pedido com carrinho e confirmação
- Autenticação básica para operadores do restaurante

# Critérios de aceite
- Visitante consegue navegar cardápio sem login
- Admin altera item e mudança aparece na vitrine em até 1 minuto
"""


def test_save_spec_rejects_long_user_phrase_as_name(tmp_path: Path):
    ws = _workspace(tmp_path)
    long_name = (
        "agora eu quero que voce me sugira as melhores respostas para criar a nossa spec"
    )
    content = _valid_spec_md().replace('"Cardápio Digital Whitelabel"', '"Spec"')
    result = save_spec(ws, long_name, content)
    assert result.startswith("Erro:")
    assert "frase" in result.lower() or "título" in result.lower()
    assert not list((tmp_path / ".pkf" / "specs").glob("*.md"))


def test_save_spec_rejects_label_list_stack(tmp_path: Path):
    ws = _workspace(tmp_path)
    content = """---
{
  "title": "Cardápio Digital",
  "status": "pending_approval",
  "suggested_stack": ["frontend", "backend", "database", "deploy"],
  "confirmed_stack": {}
}
---

# Contexto
Teste
"""
    result = save_spec(ws, "cardapio-digital", content)
    assert result.startswith("Erro")
    assert "lista" in result.lower() or "rótulos" in result.lower() or "rotulos" in result.lower()
    assert not list((tmp_path / ".pkf" / "specs").glob("*.md"))


def test_save_spec_rejects_minimal_landing_page(tmp_path: Path):
    ws = _workspace(tmp_path)
    content = """---
{
  "title": "Landing Page",
  "status": "pending_approval",
  "suggested_stack": {
    "frontend": "HTML/CSS",
    "backend": "PHP",
    "database": "MySQL",
    "deploy": "Docker"
  },
  "confirmed_stack": {}
}
---

# Contexto
Especificação da landing page.
"""
    result = save_spec(ws, "landing-page", content)
    assert result.startswith("Erro")
    assert "substância" in result.lower() or "substant" in result.lower()
    assert not list((tmp_path / ".pkf" / "specs").glob("*.md"))


def test_save_spec_accepts_valid_title_and_stack(tmp_path: Path):
    ws = _workspace(tmp_path)
    result = save_spec(ws, "cardapio-digital", _valid_spec_md())
    assert result.startswith("Spec salva")
    saved = list((tmp_path / ".pkf" / "specs").glob("*.md"))
    assert len(saved) == 1
    assert "Cardápio Digital Whitelabel" in saved[0].read_text(encoding="utf-8")
