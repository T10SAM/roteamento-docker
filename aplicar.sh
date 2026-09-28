#!/bin/bash
set -e

if [ -z "$1" ]; then
  echo "Uso: ./aplicar.sh rip   ou   ./aplicar.sh ospf"
  exit 1
fi

PROTO="$1"

if [ ! -d "configs/$PROTO" ]; then
  echo "Pasta configs/$PROTO nao encontrada."
  exit 1
fi

for R in R1 R2 R3 R4 R5; do
  echo "===== $R : aplicando $PROTO ====="
  docker cp "configs/$PROTO/$R/daemons" "$R:/etc/frr/daemons"
  docker cp "configs/$PROTO/$R/frr.conf" "$R:/etc/frr/frr.conf"
  docker exec "$R" sh -c "sed -i 's/\r$//' /etc/frr/daemons /etc/frr/frr.conf && chown frr:frr /etc/frr/daemons /etc/frr/frr.conf && chmod 640 /etc/frr/frr.conf"
  docker restart "$R"
  docker exec "$R" service frr start
done

echo "Aguardando os daemons subirem..."
sleep 10

echo ""
echo "===== Verificacao ====="
for R in R1 R2 R3 R4 R5; do
  echo "--- $R ---"
  docker exec "$R" vtysh -c "show ip route"
done