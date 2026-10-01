#!/usr/bin/env bash
# Levanta el servidor y corre E0, E1, E2 automáticamente.
# Uso: bash run_experimentos.sh
set -e

DURACION=18
TARJETAS=10
HILOS=30

run_experimento() {
  NOMBRE=$1
  WORKERS=$2
  CACHE=$3

  echo ""
  echo ">>> $NOMBRE (WORKERS=$WORKERS, CACHE_ENABLED=$CACHE)"
  WORKERS=$WORKERS CACHE_ENABLED=$CACHE python3 server.py > "server_${NOMBRE}.log" 2>&1 &
  SERVER_PID=$!
  sleep 1.5

  python3 client.py --duracion $DURACION --tarjetas $TARJETAS --hilos $HILOS --salida "${NOMBRE}.csv"

  kill $SERVER_PID
  wait $SERVER_PID 2>/dev/null || true
  sleep 1
}

run_experimento e0 1 false
run_experimento e1 8 false
run_experimento e2 8 true
run_experimento e2b 8 true

echo ""
echo "=== RESULTADOS ==="
python3 analyze.py e0.csv e1.csv e2.csv e2b.csv
