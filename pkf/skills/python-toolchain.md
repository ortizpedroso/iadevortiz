# Modern Python Toolchain

Use em projetos backend Python gerados pela PKF.

## Setup recomendado

- Python 3.11+
- FastAPI para APIs REST
- SQLite ou JSON para persistência leve em MVP
- pytest para testes
- ruff para lint (quando disponível)

## Estrutura mínima

```
app/
  main.py       # FastAPI app
  models.py     # dataclasses / pydantic
  store.py      # persistência
tests/
  test_api.py
requirements.txt
```

## Boas práticas

- Endpoints com tipos explícitos e respostas JSON consistentes
- Variáveis de ambiente para segredos (nunca commitar `.env`)
- Health check em `GET /health`
- CORS configurado se o frontend for servido separado

## Verificação

- `python -m pytest` deve passar
- API sobe com `uvicorn app.main:app --reload`
