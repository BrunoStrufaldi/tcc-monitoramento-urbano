@echo off
echo === Parando MySQL97 ===
net stop MySQL97

echo === Iniciando MySQL com --skip-grant-tables ===
net start MySQL97 --skip-grant-tables
if %errorlevel% neq 0 (
    echo Falhou com net start, tentando direto...
    "C:\Program Files\MySQL\MySQL Server 9.7\bin\mysqld.exe" --defaults-file="C:\ProgramData\MySQL\MySQL Server 9.7\my.ini" --skip-grant-tables --shared-memory MySQL97 &
    timeout /t 5
)

echo === Resetando senha root ===
"C:\Program Files\MySQL\MySQL Server 9.7\bin\mysql.exe" -u root -e "FLUSH PRIVILEGES; ALTER USER 'root'@'localhost' IDENTIFIED BY 'root'; FLUSH PRIVILEGES;"
if %errorlevel% neq 0 (
    echo ERRO ao resetar senha!
    pause
    exit /b 1
)

echo === Parando MySQL (skip-grant) ===
taskkill /F /IM mysqld.exe 2>nul
timeout /t 3

echo === Reiniciando MySQL normalmente ===
net start MySQL97

echo === Testando conexao ===
"C:\Program Files\MySQL\MySQL Server 9.7\bin\mysql.exe" -u root -proot -e "SELECT 'OK' AS conexao;"
echo.
echo === CONCLUIDO! Senha do root agora e: root ===
pause
