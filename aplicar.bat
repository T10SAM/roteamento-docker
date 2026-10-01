@echo off
setlocal

if "%~1"=="" (
  echo Uso: aplicar.bat rip      ^(RIP via FRR^)
  echo      aplicar.bat ospf     ^(OSPF via FRR^)
  echo      aplicar.bat proprio  ^(algoritmo proprio, ao vivo^)
  exit /b 1
)

set PROTO=%~1

if /I "%PROTO%"=="proprio" goto :PROPRIO

REM =====================================================================
REM  Fluxo RIP / OSPF: aplica daemons + frr.conf e reinicia o FRR
REM =====================================================================

if not exist configs\%PROTO% (
  echo Pasta configs\%PROTO% nao encontrada.
  exit /b 1
)

for %%R in (R1 R2 R3 R4 R5) do (
  echo ===== %%R : aplicando %PROTO% =====
  docker cp configs\%PROTO%\%%R\daemons %%R:/etc/frr/daemons
  docker cp configs\%PROTO%\%%R\frr.conf %%R:/etc/frr/frr.conf
  docker exec %%R sh -c "sed -i 's/\r$//' /etc/frr/daemons /etc/frr/frr.conf && chown frr:frr /etc/frr/daemons /etc/frr/frr.conf && chmod 640 /etc/frr/frr.conf"
  REM garante que o algoritmo proprio nao fique disputando as rotas com o FRR
  docker exec %%R sh -c "pkill -f main.py" >nul 2>nul
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
goto :EOF

REM =====================================================================
REM  Fluxo do algoritmo proprio: copia os scripts e inicia o agente
REM  Python em segundo plano em cada roteador (sem reiniciar o container)
REM =====================================================================
:PROPRIO

if not exist algoritmo_proprio.py (
  echo algoritmo_proprio.py nao encontrado na pasta atual.
  exit /b 1
)
if not exist main.py (
  echo main.py nao encontrado na pasta atual.
  exit /b 1
)

for %%R in (R1 R2 R3 R4 R5) do (
  echo ===== %%R : aplicando algoritmo proprio =====
  REM desliga o FRR para ele nao brigar com o agente pela tabela de rotas
  docker exec %%R service frr stop
  REM mata uma instancia anterior do agente, se houver, antes de subir outra
  docker exec %%R sh -c "pkill -f main.py" >nul 2>nul
  docker exec %%R mkdir -p /opt
  docker cp algoritmo_proprio.py %%R:/opt/algoritmo_proprio.py
  docker cp main.py %%R:/opt/main.py
  docker exec -d %%R sh -c "cd /opt && python3 main.py > /var/log/agente.log 2>&1"
)

echo Aguardando o algoritmo descobrir vizinhos e convergir...
timeout /t 20 /nobreak >nul

echo.
echo ===== Verificacao =====
for %%R in (R1 R2 R3 R4 R5) do (
  echo --- %%R : tabela de rotas do kernel ---
  docker exec %%R ip route
  echo --- %%R : ultimas linhas do log do agente ---
  docker exec %%R tail -n 15 /var/log/agente.log
  echo.
)
goto :EOF