# PKF — IA de Desenvolvimento

Assistente multiagente para **especificar**, **implementar**, **revisar** e **testar** código.

Documentação completa: **[PKF.md](PKF.md)** · Deploy: **[DEPLOY.md](DEPLOY.md)**

## Início rápido

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env

cd frontend && npm install && npm run build && cd ..
python -m pkf --ui
```

Acesse `http://127.0.0.1:8765/?token=SEU_TOKEN` (se `PKF_AUTH_TOKEN` estiver definido).

## Comandos no chat

| Comando | Função |
|---------|--------|
| `/spec` | Gera especificação do projeto |
| `/build` | Implementa conforme a spec (após aprovação) |
| `/review` | Revisa código vs spec |
| `/goal` | Define meta de parada do build |

## Stack

Python 3.12 · FastAPI · React 19 · PostgreSQL · Docker · 9Router (opcional)

## Licença

MIT — ver repositório.
