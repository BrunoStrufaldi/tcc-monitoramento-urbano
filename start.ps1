$root = $PSScriptRoot
$backendPython = Join-Path $root "backend\venv\Scripts\python.exe"
$systemPython = "C:\Python314\python.exe"

if (-not (Test-Path $backendPython)) {
    Write-Error "venv do backend nao encontrado em backend\venv. Rode primeiro: cd backend; python -m venv venv; venv\Scripts\pip install -r requirements.txt"
    exit 1
}

Start-Process -FilePath "powershell" `
    -ArgumentList "-NoExit", "-Command", "& '$backendPython' -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000" `
    -WorkingDirectory (Join-Path $root "backend")

Start-Process -FilePath "powershell" `
    -ArgumentList "-NoExit", "-Command", "& '$systemPython' -m http.server 5500 -d frontend" `
    -WorkingDirectory $root

Start-Sleep -Seconds 2
Start-Process "http://localhost:5500"

Write-Output "Backend em http://localhost:8000 | Frontend em http://localhost:5500"
Write-Output "Duas janelas novas foram abertas com os logs. Feche-as (ou Ctrl+C dentro delas) para encerrar."
