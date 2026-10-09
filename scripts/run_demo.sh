#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

# Ports (8000 and 8001 are taken by host services, so we use 8003, 8002, 8004)
PORT_HONEST=8003
PORT_SLOPPY=8002
PORT_DASHBOARD=8004

if [ -f ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  PYTHON="python"
fi

# Clean old demo state
rm -rf buyer/state
mkdir -p buyer/state

echo "==> Starting Seller Honest (ProÚčetní) on port $PORT_HONEST..."
FIRM_PROFILE=honest PORT=$PORT_HONEST PAYMENT_MODE=off $PYTHON -m seller.app > /tmp/seller_honest.log 2>&1 &
PID_HONEST=$!

echo "==> Starting Seller Sloppy (CheapBooks) on port $PORT_SLOPPY..."
FIRM_PROFILE=sloppy PORT=$PORT_SLOPPY PAYMENT_MODE=off $PYTHON -m seller.app > /tmp/seller_sloppy.log 2>&1 &
PID_SLOPPY=$!

echo "==> Starting Buyer Dashboard on port $PORT_DASHBOARD..."
PORT=$PORT_DASHBOARD EVENTS_PATH=buyer/state/events.jsonl $PYTHON -m buyer.dashboard.app > /tmp/buyer_dash.log 2>&1 &
PID_DASHBOARD=$!

cleanup() {
  echo "==> Stopping background servers..."
  kill $PID_HONEST $PID_SLOPPY $PID_DASHBOARD 2>/dev/null || true
}
trap cleanup EXIT

echo "==> Waiting for services to become ready..."
for i in {1..30}; do
  if curl -s "http://127.0.0.1:$PORT_HONEST/availability" > /dev/null && \
     curl -s "http://127.0.0.1:$PORT_SLOPPY/availability" > /dev/null && \
     curl -s "http://127.0.0.1:$PORT_DASHBOARD/history" > /dev/null; then
    echo "==> All services ready!"
    break
  fi
  sleep 0.2
done

echo "==> Running Buyer Orchestrator demo scenario..."
export SELLER_URLS="http://127.0.0.1:$PORT_SLOPPY,http://127.0.0.1:$PORT_HONEST"
$PYTHON -m buyer.orchestrator --scenario demo --pace 0.1

echo "==> Demo run completed successfully!"
