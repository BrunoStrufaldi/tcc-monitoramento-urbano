$root = $PSScriptRoot
$backendPython = Join-Path $root "backend\venv\Scripts\python.exe"

if (-not (Test-Path $backendPython)) {
    Write-Error "venv do backend nao encontrado em backend\venv. Rode primeiro: cd backend; python -m venv venv; venv\Scripts\pip install -r requirements.txt"
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
