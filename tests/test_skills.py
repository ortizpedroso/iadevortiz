from pkf.skills.search import search_skills, resolve_skills


def test_search_skills_frontend():
    ranked = search_skills("landing page interface design")
    assert ranked
    assert any("frontend" in s.skill_id for s, _ in ranked)


def test_resolve_skills_by_slug():
    text = resolve_skills("cardápio digital restaurante", "cardapio-digital")
    assert text
    assert "whitelabel" in text.lower() or "card" in text.lower()
