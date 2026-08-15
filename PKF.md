# PKF — IA de Desenvolvimento

Assistente multiagente para especificar, implementar, revisar e testar código no seu workspace.

## O que ela faz

- Roteia o pedido para um especialista: `architect`, `frontend`, `backend`, `logic`, `reviewer`, `tester` ou `generalista`
- Segue o ciclo `/spec` → `/build` → `/review`
- Lê e escreve arquivos, busca código e roda comandos permitidos
- Compacta conversas longas em agentes de memória
- Fala com Ollama (local), Kimi/Moonshot ou OpenAI

## Como usar

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Interface web (estilo Cursor/Claude):

```bash
python -m pkf --ui
```

Abre `http://127.0.0.1:8765`. O terminal continua disponível sem `--ui`.

Ollama local (padrão):

```bash
python -m pkf
```

Kimi, com fallback para Ollama se a cota acabar:

```bash
python -m pkf kimi
```

Workspace específico:

```bash
python -m pkf ollama --workspace C:\projetos\meu-app
```

O script antigo `python test_vps_ai.py` continua funcionando e só abre o mesmo CLI.

## Deploy na VPS (Hostinger)

Para não rodar o modelo pesado no seu PC, suba na VPS com Docker + API Kimi/OpenAI:

```bash
# Na VPS
cd /opt/pkf
cp .env.production.example .env   # preencha MOONSHOT_API_KEY e PKF_AUTH_TOKEN
bash deploy/hostinger/setup.sh
```

Guia completo: [DEPLOY.md](DEPLOY.md)

## Comandos

| Comando | Função |
|---|---|
| `/spec [nome]` | Entrevista e grava a spec em `.pkf/specs` |
| `/build [nome]` | Implementa a spec ativa |
| `/review` | Compara código e spec |
| `/status` | Fase, spec e último agente |
| `/agents` | Agentes carregados |
| `/workspace` | Resumo do projeto |
| `/graph` | Exporta o grafo da conversa |
| `sair` | Encerra |

## Segurança

As ferramentas ficam presas ao workspace. Arquivos de segredo (`.env`, chaves) não são lidos nem escritos. O terminal só aceita uma allowlist (`python`, `pytest`, `npm`, `git status/diff/log`, etc.).
