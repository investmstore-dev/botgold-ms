@echo off
REM BOT Mining Store GOLD - inicia bot y dashboard en segundo plano (sin ventanas)
powershell -NoProfile -Command "if (-not (Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {$_.CommandLine -like '*logic.bot*'})) { Start-Process python -ArgumentList '-m','logic.bot' -WorkingDirectory 'C:\Users\NLope\Documents\repolocal-claude\botgold-ms' -WindowStyle Hidden }"
powershell -NoProfile -Command "if (-not (Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {$_.CommandLine -like '*http.server*'})) { Start-Process python -ArgumentList '-m','http.server','8080' -WorkingDirectory 'C:\Users\NLope\Documents\repolocal-claude' -WindowStyle Hidden }"
echo Bot y dashboard corriendo en segundo plano.
echo Dashboard: http://localhost:8080/botgold-dashboard-ms/
