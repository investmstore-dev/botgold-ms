@echo off
REM BOT Mining Store GOLD - detiene bot y dashboard
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {$_.CommandLine -like '*logic.bot*' -or $_.CommandLine -like '*bot.py*' -or $_.CommandLine -like '*http.server*'} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Bot y dashboard detenidos.
