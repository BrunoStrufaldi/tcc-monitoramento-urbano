$root = $PSScriptRoot
$backendPython = Join-Path $root "backend\venv\Scripts\python.exe"

if (-not (Test-Path $backendPython)) {
    Write-Error "venv do backend nao encontrado em backend\venv. Rode primeiro: cd backend; python -m venv venv; venv\Scripts\pip install -r requirements.txt"
    exit 1
}

# No Windows o uvicorn consegue abrir a porta 8000 mesmo ocupada. Uma segunda
# copia rodaria outro ciclo de monitoramento no mesmo banco.
if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    Write-Warning "O backend ja esta rodando na porta 8000. Feche a janela dele antes de abrir outra copia."
    Start-Process "http://localhost:8000"
    exit 1
}

# Um processo so: o FastAPI serve a API e o painel (frontend/) na mesma porta.
Start-Process -FilePath "powershell" `
    -ArgumentList "-NoExit", "-Command", "& '$backendPython' -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000" `
    -WorkingDirectory (Join-Path $root "backend")

Start-Sleep -Seconds 3
Start-Process "http://localhost:8000"

Write-Output "Painel e API em http://localhost:8000 (status: /api/status, docs: /docs)"
Write-Output "Os logs estao na janela nova. Feche-a (ou Ctrl+C dentro dela) para encerrar."
