# Contribuindo com a PKF

Obrigado por contribuir com o projeto **PKF** (IA de Desenvolvimento).

## Como reportar bugs

Abra uma issue descrevendo:

- O que você esperava
- O que aconteceu
- Passos para reproduzir
- Logs relevantes (sem expor chaves de API)

## Desenvolvimento

```bash
pip install -r requirements-dev.txt
cd frontend && npm install && npm run dev
python -m pkf --ui
```

Execute `pytest` antes de enviar PRs.

## Segurança

Nunca commite `.env`, `secrets.env` ou chaves de API. Use os arquivos `.example` como referência.
