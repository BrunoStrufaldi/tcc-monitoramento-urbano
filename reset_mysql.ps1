Stop-Service MySQL97 -Force -ErrorAction SilentlyContinue
Start-Sleep 3
Start-Process "C:\Program Files\MySQL\MySQL Server 9.7\bin\mysqld.exe" -ArgumentList "--defaults-file=`"C:\ProgramData\MySQL\MySQL Server 9.7\my.ini`" --skip-grant-tables --shared-memory" -NoNewWindow
Start-Sleep 5
& "C:\Program Files\MySQL\MySQL Server 9.7\bin\mysql.exe" -u root -e "FLUSH PRIVILEGES; ALTER USER 'root'@'localhost' IDENTIFIED BY 'root'; FLUSH PRIVILEGES;"
taskkill /F /IM mysqld.exe 2>$null
Start-Sleep 3
Start-Service MySQL97
Start-Sleep 3
& "C:\Program Files\MySQL\MySQL Server 9.7\bin\mysql.exe" -u root -proot -e "SELECT 'OK' AS conexao;"
