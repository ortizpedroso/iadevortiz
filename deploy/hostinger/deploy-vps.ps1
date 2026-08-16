# Envia update para a VPS (requer SSH configurado)
# Uso: .\deploy\hostinger\deploy-vps.ps1
#      .\deploy\hostinger\deploy-vps.ps1 -Host root@187.77.240.125

param(
    [string]$SshHost = "root@187.77.240.125",
    [string]$Key = "$env:USERPROFILE\.ssh\pkf_vps",
    [string]$RemoteDir = "/opt/pkf"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$sshArgs = @("-o", "StrictHostKeyChecking=accept-new")
if (Test-Path $Key) { $sshArgs += @("-i", $Key) }

Write-Host "==> Git push local (se houver commits pendentes)"
Push-Location $root
$ErrorActionPreference = 'Continue'
git push origin main | Out-Null
$ErrorActionPreference = 'Stop'
Pop-Location

Write-Host "==> Enviar secrets.env para VPS"
if (Test-Path (Join-Path $PSScriptRoot "secrets.env")) {
    & scp @sshArgs (Join-Path $PSScriptRoot "secrets.env") "${SshHost}:${RemoteDir}/deploy/hostinger/secrets.env"
}

Write-Host "==> SSH: git pull + update na VPS ($SshHost)"
$remote = @"
set -e
cd $RemoteDir
git pull origin main
SECRETS_FILE=$RemoteDir/deploy/hostinger/secrets.env bash deploy/hostinger/set-env-keys.sh
bash deploy/hostinger/update.sh
curl -s http://127.0.0.1:8765/api/health | head -c 500
echo ''
"@

& ssh @sshArgs $SshHost $remote
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "SSH falhou. Cole na VPS (root@srv1770462):" -ForegroundColor Yellow
    Write-Host "  cd /opt/pkf && git pull origin main && bash deploy/hostinger/update.sh"
    exit 1
}

Write-Host ""
Write-Host "PKF: http://187.77.240.125:8765/?token=teste123" -ForegroundColor Green
