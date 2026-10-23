<#
.SYNOPSIS
    Publica o MotSP no Google Cloud Run (API, painel e YOLO numa imagem só).

.DESCRIPTION
    O serviço não fica ligado quando ninguém está usando, então não gera custo
    parado. Ele liga no primeiro acesso e desliga sozinho uns 15 min depois.

    Só pode existir uma instância por vez, porque o banco é um SQLite dentro do
    container. Isso também limita o gasto.

    A TOMTOM_API_KEY é lida do backend/.env na hora do deploy. Ela não fica
    escrita neste script nem vai para dentro da imagem.

    As variáveis já configuradas na nuvem são mantidas. O monitoramento só muda
    se for usado -Monitoramento ou -DesligarMonitoramento.

    Este é o deploy manual. O automático roda a cada push na main (cloudbuild.yaml).

.EXAMPLE
    .\deploy.ps1 -ProjectId motsp-tcc
    .\deploy.ps1 -ProjectId motsp-tcc -Monitoramento
    .\deploy.ps1 -ProjectId motsp-tcc -DesligarMonitoramento
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,

    [string]$Service = "motsp",

    # southamerica-east1 é São Paulo, mais perto das câmeras e de quem usa o painel.
    [string]$Region = "southamerica-east1",

    # Liga o monitoramento das câmeras. Sem esta opção, o que já está na nuvem
    # continua como está.
    [switch]$Monitoramento,

    # Desliga o monitoramento das câmeras.
    [switch]$DesligarMonitoramento,

    # Pula a ativação das APIs, que só é preciso na primeira vez.
    [switch]$PularApis
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Error "gcloud nao encontrado. Instale o Google Cloud CLI e rode 'gcloud init' antes."
    exit 1
}

foreach ($peso in @("ml/models/gx-veiculos.pt", "ml/models/yolo11m.pt", "ml/models/gx-incident.pt")) {
    if (-not (Test-Path $peso)) {
        Write-Error "Peso ausente: $peso. A imagem subiria sem deteccao real."
        exit 1
    }
}

Write-Host "==> Projeto: $ProjectId | Servico: $Service | Regiao: $Region" -ForegroundColor Cyan
gcloud config set project $ProjectId | Out-Null

if (-not $PularApis) {
    Write-Host "==> Habilitando APIs (Cloud Run, Cloud Build, Artifact Registry)..." -ForegroundColor Cyan
    gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
    if (-not $?) { Write-Error "Falha ao habilitar as APIs. O faturamento do projeto esta ativo?"; exit 1 }
}

# --- Permissão para o Cloud Build ------------------------------------------
# Projetos novos do Google Cloud não dão essa permissão sozinhos, e sem ela o
# build falha. Rodar de novo não duplica nada.
$numero = (gcloud projects describe $ProjectId --format "value(projectNumber)")
$contaBuild = "serviceAccount:$numero-compute@developer.gserviceaccount.com"
Write-Host "==> Garantindo papel cloudbuild.builds.builder para $contaBuild..." -ForegroundColor Cyan
gcloud projects add-iam-policy-binding $ProjectId --member $contaBuild --role roles/cloudbuild.builds.builder --condition=None | Out-Null
if (-not $?) { Write-Error "Nao consegui conceder o papel ao Cloud Build."; exit 1 }

# --- TOMTOM_API_KEY: lida do .env local, nunca vai para o Git --------------
$tomtom = ""
if (Test-Path "backend/.env") {
    $linha = Select-String -Path "backend/.env" -Pattern '^\s*TOMTOM_API_KEY\s*=\s*(.+)$' |
             Select-Object -First 1
    if ($linha) { $tomtom = $linha.Matches[0].Groups[1].Value.Trim().Trim('"') }
}
if (-not $tomtom) {
    Write-Warning "TOMTOM_API_KEY nao encontrada em backend/.env. Sem ela o transito e decidido so pela contagem."
}

if ($Monitoramento -and $DesligarMonitoramento) {
    Write-Error "Escolha -Monitoramento OU -DesligarMonitoramento, nao os dois."
    exit 1
}

# Variáveis que o script sempre define. O resto continua como está na nuvem.
$pares = @(
    "DATABASE_URL=sqlite:///./gx.db",
    # Na nuvem não tem GPU, então a detecção é mais lenta e o intervalo é maior.
    "GX_LIVE_DETECTION_INTERVAL_SECONDS=60"
)
# Só manda a chave se ela foi encontrada, para não apagar a que já está na nuvem.
if ($tomtom) { $pares += "TOMTOM_API_KEY=$tomtom" }

$ativo = "(preservado)"
if ($Monitoramento -or $DesligarMonitoramento) {
    $ativo = if ($Monitoramento) { "true" } else { "false" }
    $pares += @(
        "GX_MONITORAMENTO_ATIVO=$ativo",
        "GX_TRANSITO_MONITORAR_CATALOGO=$ativo",
        "GX_ALAGAMENTO_MONITORAR_CATALOGO=$ativo"
    )
}

# Separador ^@^ para o gcloud não quebrar valores que têm vírgula.
$envVars = "^@^" + ($pares -join "@")

# Instalar o torch demora mais que os 10 min padrão do Cloud Build.
gcloud config set builds/timeout 1800 | Out-Null

Write-Host "==> Build + deploy (a primeira vez leva ~10 min: instala o torch)..." -ForegroundColor Cyan
gcloud run deploy $Service `
    --source . `
    --region $Region `
    --platform managed `
    --allow-unauthenticated `
    --memory 4Gi `
    --cpu 2 `
    --min-instances 0 `
    --max-instances 1 `
    --concurrency 40 `
    --timeout 3600 `
    --update-env-vars $envVars

if (-not $?) { Write-Error "Deploy falhou. Veja o log do Cloud Build no link acima."; exit 1 }

$url = (gcloud run services describe $Service --region $Region --format "value(status.url)")
Write-Host ""
Write-Host "==> No ar: $url" -ForegroundColor Green
Write-Host "    Monitoramento continuo: $ativo"
Write-Host "    Status da API:          $url/api/status"
Write-Host "    Estado do YOLO:         $url/deteccao/status"
