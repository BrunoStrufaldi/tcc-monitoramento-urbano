<#
.SYNOPSIS
    Publica o MotSP no Google Cloud Run (uma imagem: API + painel + YOLO).

.DESCRIPTION
    O serviço sobe com min-instances=0: nenhuma instância fica de pé quando
    ninguém está acessando, e o Google não cobra por isso. A instância nasce na
    primeira requisição do link e morre sozinha ~15 min depois da última.

    max-instances=1 é proposital e importante: o banco é um SQLite dentro do
    container, então duas instâncias simultâneas teriam dados diferentes — e é
    também o teto de gasto, impedindo que um pico de acessos multiplique a conta.

    A TOMTOM_API_KEY é lida do backend/.env na hora do deploy e enviada como
    variável de ambiente do serviço. Ela nunca é escrita neste script nem vai
    para dentro da imagem (o .dockerignore exclui o .env).

    As variáveis são enviadas com --update-env-vars (mescla), não --set-env-vars
    (substitui). Isso importa: o monitoramento contínuo e qualquer ajuste feito
    depois com `gcloud run services update` sobrevivem a um redeploy. Sem
    -Monitoramento nem -DesligarMonitoramento o script não toca nesse estado.

    Este script é o caminho MANUAL. O automático é o gatilho do Cloud Build
    (cloudbuild.yaml), que publica a cada push na main do GitHub.

.EXAMPLE
    .\deploy.ps1 -ProjectId motsp-tcc
    .\deploy.ps1 -ProjectId motsp-tcc -Monitoramento
    .\deploy.ps1 -ProjectId motsp-tcc -DesligarMonitoramento
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,

    [string]$Service = "motsp",

    # southamerica-east1 = São Paulo (menor latência para as câmeras da CET e
    # para quem abrir o link no Brasil). us-central1 é mais barato por
    # vCPU-segundo se o crédito ficar apertado.
    [string]$Region = "southamerica-east1",

    # Liga as threads de detecção contínua (trânsito + alagamento) no serviço.
    # Sem esta flag o estado atual da nuvem é PRESERVADO — um redeploy nunca
    # desliga o monitoramento por acidente.
    [switch]$Monitoramento,

    # Desliga as threads explicitamente. É o único jeito de desligar por aqui.
    [switch]$DesligarMonitoramento,

    # Pula o "enable services" (só precisa na primeira vez; leva ~1 min).
    [switch]$PularApis
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Error "gcloud nao encontrado. Instale o Google Cloud CLI e rode 'gcloud init' antes."
    exit 1
}

foreach ($peso in @("ml/models/yolo11m.pt", "ml/models/gx-incident.pt")) {
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

# --- Permissao para o Cloud Build --------------------------------------------
# Em projetos criados a partir de 2024 a conta de servico padrao do Compute
# (<numero>-compute@developer.gserviceaccount.com) nao recebe mais o papel
# Editor automaticamente — e e ela que o `gcloud run deploy --source` usa para
# ler o zip do codigo e publicar a imagem. Sem este papel a build morre com
# "PERMISSION_DENIED ... could not resolve source". Idempotente: repetir nao duplica.
$numero = (gcloud projects describe $ProjectId --format "value(projectNumber)")
$contaBuild = "serviceAccount:$numero-compute@developer.gserviceaccount.com"
Write-Host "==> Garantindo papel cloudbuild.builds.builder para $contaBuild..." -ForegroundColor Cyan
gcloud projects add-iam-policy-binding $ProjectId --member $contaBuild --role roles/cloudbuild.builds.builder --condition=None | Out-Null
if (-not $?) { Write-Error "Nao consegui conceder o papel ao Cloud Build."; exit 1 }

# --- TOMTOM_API_KEY: lida do .env local, nunca versionada -------------------
$tomtom = ""
if (Test-Path "backend/.env") {
    $linha = Select-String -Path "backend/.env" -Pattern '^\s*TOMTOM_API_KEY\s*=\s*(.+)$' |
             Select-Object -First 1
    if ($linha) { $tomtom = $linha.Matches[0].Groups[1].Value.Trim().Trim('"') }
}
if (-not $tomtom) {
    Write-Warning "TOMTOM_API_KEY nao encontrada em backend/.env — a arbitragem de transito vai degradar."
}

if ($Monitoramento -and $DesligarMonitoramento) {
    Write-Error "Escolha -Monitoramento OU -DesligarMonitoramento, nao os dois."
    exit 1
}

# Variaveis que este script sempre garante (idempotentes: mesmo valor a cada
# deploy). Tudo que NAO esta aqui e preservado como esta na nuvem.
$pares = @(
    "GX_SERVE_FRONTEND=true",
    "DATABASE_URL=sqlite:///./gx.db",
    # 15s (valor local, com GPU) viraria fila infinita em CPU: cada inferencia
    # do yolo11m a 1280 leva alguns segundos por camera.
    "GX_LIVE_DETECTION_INTERVAL_SECONDS=60"
)
# So sobrescreve a chave se ela foi encontrada: um .env sem a chave nao pode
# apagar a que ja esta configurada no servico.
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

# Delimitador customizado (^@^): evita que o gcloud quebre valores em virgulas.
$envVars = "^@^" + ($pares -join "@")

# O Cloud Build assume 10 min por build; instalar o torch passa disso com
# folga e a build morreria no meio, sem imagem e sem mensagem clara.
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
