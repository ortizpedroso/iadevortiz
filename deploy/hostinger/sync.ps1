# Envia o projeto para a VPS (sem pastas pesadas)
# Uso: .\deploy\hostinger\sync.ps1 -Host user@IP_DA_VPS

param(
    [Parameter(Mandatory = $true)]
    [string]$Host,
    [string]$RemoteDir = "/opt/pkf"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")

Write-Host "Enviando de $root para ${Host}:${RemoteDir}"

$excludes = @(
    ".venv", "venv", "__pycache__", ".git", ".pkf",
    "system_prompts_leaks", "Anthropic", "OpenAI", "Google", "xAI",
    "Perplexity", "Microsoft", "Cursor", "Meta", "Mistral", "Kimi",
    "DeepSeek", "GLM", "OpenCode", "Pi", "Notion", "Qwen", "Misc",
    "assets", ".github", "knowledge_graph.png", ".env"
)

if (Get-Command rsync -ErrorAction SilentlyContinue) {
    $excludeArgs = $excludes | ForEach-Object { "--exclude=$_" }
    rsync -avz --delete @excludeArgs "$root/" "${Host}:${RemoteDir}/"
} else {
    Write-Host "rsync não encontrado. Instale (Git for Windows / WSL) ou use scp manualmente."
    Write-Host "Alternativa: git clone na VPS a partir do seu repositório."
    exit 1
}

Write-Host "Concluído. Na VPS: cd $RemoteDir && cp .env.production.example .env && nano .env && bash deploy/hostinger/setup.sh"
