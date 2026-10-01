#!/bin/bash
set -e

if [ -z "$1" ]; then
  echo "Uso: ./aplicar.sh rip      (RIP via FRR)"
  echo "     ./aplicar.sh ospf     (OSPF via FRR)"
  echo "     ./aplicar.sh proprio  (algoritmo proprio, ao vivo)"
  exit 1
fi

PROTO="$1"
ROTEADORES="R1 R2 R3 R4 R5"

if [ "$PROTO" = "proprio" ]; then

  # =====================================================================
  #  Fluxo do algoritmo proprio: copia os scripts e inicia o agente
  #  Python em segundo plano em cada roteador (sem reiniciar o container)
  # =====================================================================

  if [ ! -f algoritmo_proprio.py ]; then
    echo "algoritmo_proprio.py nao encontrado na pasta atual."
    exit 1
  fi
  if [ ! -f main.py ]; then
    echo "main.py nao encontrado na pasta atual."
    exit 1
  fi

  for R in $ROTEADORES; do
    echo "===== $R : aplicando algoritmo proprio ====="
    # desliga o FRR para ele nao brigar com o agente pela tabela de rotas
    docker exec "$R" service frr stop
    # mata uma instancia anterior do agente, se houver, antes de subir outra
    docker exec "$R" sh -c "pkill -f main.py" || true
    docker exec "$R" mkdir -p /opt
    docker cp algoritmo_proprio.py "$R:/opt/algoritmo_proprio.py"
    docker cp main.py "$R:/opt/main.py"
    docker exec -d "$R" sh -c "cd /opt && python3 main.py > /var/log/agente.log 2>&1"
  done

  echo "Aguardando o algoritmo descobrir vizinhos e convergir..."
  sleep 20

  echo ""
  echo "===== Verificacao ====="
  for R in $ROTEADORES; do
    echo "--- $R : tabela de rotas do kernel ---"
    docker exec "$R" ip route
    echo "--- $R : ultimas linhas do log do agente ---"
    docker exec "$R" tail -n 15 /var/log/agente.log
    echo ""
  done

else

  # =====================================================================
  #  Fluxo RIP / OSPF: aplica daemons + frr.conf e reinicia o FRR
  # =====================================================================

  if [ ! -d "configs/$PROTO" ]; then
    echo "Pasta configs/$PROTO nao encontrada."
    exit 1
  fi

  for R in $ROTEADORES; do
    echo "===== $R : aplicando $PROTO ====="
    docker cp "configs/$PROTO/$R/daemons" "$R:/etc/frr/daemons"
    docker cp "configs/$PROTO/$R/frr.conf" "$R:/etc/frr/frr.conf"
    docker exec "$R" sh -c "sed -i 's/\r$//' /etc/frr/daemons /etc/frr/frr.conf && chown frr:frr /etc/frr/daemons /etc/frr/frr.conf && chmod 640 /etc/frr/frr.conf"
    # garante que o algoritmo proprio nao fique disputando as rotas com o FRR
    docker exec "$R" sh -c "pkill -f main.py" || true
    docker restart "$R"
    docker exec "$R" service frr start
  done

  echo "Aguardando os daemons subirem..."
  sleep 10

  echo ""
  echo "===== Verificacao ====="
  for R in $ROTEADORES; do
    echo "--- $R ---"
    docker exec "$R" vtysh -c "show ip route"
  done

fi