# Deploy na VPS Hostinger

Rode a PKF na VPS para **não travar seu PC**. Na VPS usamos **API na nuvem (Kimi/OpenAI)**, não Ollama local — modelos locais consomem muita RAM.

## Requisitos na VPS

- Ubuntu 22.04+ (VPS Hostinger)
- 2 GB RAM mínimo (4 GB recomendado)
- Acesso SSH (`root` ou usuário sudo)
- Chave **MOONSHOT_API_KEY** (Kimi) ou **OPENAI_API_KEY**

## Passo a passo

### 1. Conectar na VPS

```bash
ssh root@SEU_IP_DA_VPS
```

### 2. Enviar o projeto

**Opção A — Git (recomendado)**

```bash
sudo mkdir -p /opt/pkf
sudo chown $USER:$USER /opt/pkf
cd /opt/pkf
git clone SEU_REPOSITORIO .
```

**Opção B — Do seu Windows (rsync)**

```powershell
cd C:\projetos\PKF
.\deploy\hostinger\sync.ps1 -Host root@SEU_IP_DA_VPS
```

### 3. Configurar variáveis

```bash
cd /opt/pkf
cp .env.production.example .env
nano .env
```

Preencha pelo menos:

- `MOONSHOT_API_KEY` — sua chave Kimi
- `PKF_AUTH_TOKEN` — token forte (ex.: `openssl rand -hex 32`)

### 4. Subir com Docker

**Só PKF (Groq/Gemini direto):**

```bash
bash deploy/hostinger/setup.sh
```

**PKF + 9Router (recomendado — pool free maior):**

```bash
docker compose --profile router build
docker compose --profile router up -d
```

Configure no `.env`:

```env
NINEROUTER_URL=http://ninerouter:20128
PKF_PROVIDER=ninerouter
NINEROUTER_MODEL=oc/big-pickle
GROQ_API_KEY=...    # fallback se 9Router cair
```

No dashboard 9Router (`ssh -L 20128:127.0.0.1:20128 root@VPS`): conecte OpenCode Free + combo free.

Ou manualmente:

```bash
docker compose build
docker compose up -d
docker compose logs -f pkf
```

### 5. Acessar no navegador

**Direto na API (recomendado na VPS com Caddy na porta 80):**

```
http://SEU_IP:8765/?token=SEU_PKF_AUTH_TOKEN
```

**Via Nginx do compose (porta 8080 — evita conflito com Caddy/eventosbr na :80):**

```
http://SEU_IP:8080/?token=SEU_PKF_AUTH_TOKEN
```

O token fica salvo no navegador após o primeiro acesso.

## Comandos úteis

```bash
docker compose ps
docker compose logs -f pkf
docker compose restart pkf
docker compose down
docker compose up -d --build
```

## Domínio e HTTPS (opcional)

1. Aponte o DNS do domínio para o IP da VPS.
2. Instale Certbot na VPS e configure SSL no nginx (substitua `deploy/nginx/pkf.conf` por versão com `listen 443 ssl`).

## Por que não Ollama na VPS?

| Ambiente | Modelo | RAM típica |
|---|---|---|
| Seu PC | Ollama `llama3:8b` | ~8 GB+ (trava máquinas fracas) |
| VPS | Kimi / OpenAI API | ~200 MB (só a app Python) |

## Estrutura na VPS

```
/opt/pkf/
├── .env              # segredos (não commitar)
├── docker-compose.yml
├── Dockerfile
└── deploy/
```

Dados persistentes (specs, chat, memória): volume Docker `pkf-workspace` em `/data/workspace/.pkf/`.

## Troubleshooting

**Connection error / provider_ok: false**  
→ Confira `MOONSHOT_API_KEY` no `.env` e reinicie: `docker compose restart pkf`

**401 Token inválido**  
→ Acesse com `?token=` igual ao `PKF_AUTH_TOKEN` do `.env`

**Porta 80 fechada ou em uso (Caddy/eventosbr)**  
→ Use `http://SEU_IP:8765` ou `http://SEU_IP:8080` (nginx do compose). Não altere o Caddy existente.

**Porta 80 fechada no firewall**  
→ Hostinger: libere HTTP no firewall do painel + `sudo ufw allow 80/tcp`
