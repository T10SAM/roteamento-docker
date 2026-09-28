@echo off
setlocal

if "%~1"=="" (
  echo Uso: aplicar.bat rip   ou   aplicar.bat ospf
  exit /b 1
)

set PROTO=%~1

if not exist configs\%PROTO% (
  echo Pasta configs\%PROTO% nao encontrada.
  exit /b 1
)

for %%R in (R1 R2 R3 R4 R5) do (
  echo ===== %%R : aplicando %PROTO% =====
  docker cp configs\%PROTO%\%%R\daemons %%R:/etc/frr/daemons
  docker cp configs\%PROTO%\%%R\frr.conf %%R:/etc/frr/frr.conf
  docker exec %%R sh -c "sed -i 's/\r$//' /etc/frr/daemons /etc/frr/frr.conf && chown frr:frr /etc/frr/daemons /etc/frr/frr.conf && chmod 640 /etc/frr/frr.conf"
  docker restart %%R
  docker exec %%R service frr start
)

echo Aguardando os daemons subirem...
timeout /t 10 /nobreak >nul

echo.
echo ===== Verificacao =====
for %%R in (R1 R2 R3 R4 R5) do (
  echo --- %%R ---
  docker exec %%R vtysh -c "show ip route"
)
