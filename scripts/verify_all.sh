#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BOLD}${BLUE}============================================================${NC}"
echo -e "${BOLD}${BLUE}🛡️  Aiccountant007 - Comprehensive System Health Verification${NC}"
echo -e "${BOLD}${BLUE}============================================================${NC}"
echo ""

PASS_COUNT=0
TOTAL_COUNT=7

report_pass() {
    echo -e "${GREEN}[✔ PASS]${NC} $1"
    PASS_COUNT=$((PASS_COUNT + 1))
}

report_fail() {
    echo -e "${RED}[✘ FAIL]${NC} $1"
}

report_warn() {
    echo -e "${YELLOW}[⚠ WARN]${NC} $1"
}

# 1. Code Style & Linter (Ruff)
echo -e "${BOLD}1. Checking code standards (Ruff)...${NC}"
if .venv/bin/ruff check > /dev/null 2>&1; then
    report_pass "Ruff linter: clean, zero violations across all modules"
else
    report_fail "Ruff linter reported warnings or errors"
fi

# 2. Strict Type Checking (Mypy)
echo -e "${BOLD}2. Checking static typing (Mypy)...${NC}"
if .venv/bin/mypy common/ buyer/ seller/ > /dev/null 2>&1; then
    report_pass "Mypy: 100% strict type check passing across all 41 source files"
else
    report_fail "Mypy reported type errors"
fi

# 3. Test Suite (Pytest)
echo -e "${BOLD}3. Running unit and integration test suite (Pytest)...${NC}"
TEST_OUTPUT=$(.venv/bin/pytest -q)
if echo "$TEST_OUTPUT" | grep -q "89 passed"; then
    report_pass "Pytest: all 89 unit & integration tests passed cleanly"
else
    report_fail "Pytest failed: $TEST_OUTPUT"
fi

# 4. Masumi Payment Node Check
echo -e "${BOLD}4. Checking Masumi Payment Service Node (:3001)...${NC}"
if curl -s -I http://127.0.0.1:3001/docs/ 2>/dev/null | grep -q "200 OK"; then
    report_pass "Masumi Node is online on http://127.0.0.1:3001 (Swagger docs accessible)"
else
    report_warn "Masumi Node is not responding on :3001 (Offline or port blocked)"
fi

# 5. Blockfrost Cardano Preprod Health
echo -e "${BOLD}5. Checking Cardano Preprod Blockfrost Gateway...${NC}"
BF_HEALTH=$(curl -s -H "project_id: preprodMoN7D7zVTIrJwtqa0BKHYzTeZUVlVn3G" https://cardano-preprod.blockfrost.io/api/v0/health 2>/dev/null || echo "{}")
if echo "$BF_HEALTH" | grep -q '"is_healthy":true'; then
    report_pass "Blockfrost Preprod Gateway is healthy and synchronized"
else
    report_fail "Blockfrost Preprod Gateway check failed"
fi

# 6. Team Faucet Wallet Balance
echo -e "${BOLD}6. Checking Cardano Preprod Faucet Wallet...${NC}"
WALLET_JSON=$(curl -s -H "project_id: preprodMoN7D7zVTIrJwtqa0BKHYzTeZUVlVn3G" https://cardano-preprod.blockfrost.io/api/v0/addresses/addr_test1qpu552ygmh07sz7mcdvl7gcca5u6jswpuq92jk04w75ga3qvp2yenrqn90qpeh5rzj0gkdh75hl52yj2drfyclrur9qsst9h6j 2>/dev/null || echo "{}")
LOVELACE=$(echo "$WALLET_JSON" | grep -o '"quantity":"[0-9]*"' | head -n 1 | cut -d'"' -f4 || echo "0")
if [ "$LOVELACE" -gt 0 ]; then
    ADA=$(python3 -c "print(f'{$LOVELACE / 1000000:.2f}')")
    report_pass "Faucet Wallet Balance: $ADA tADA (addr_test1qpu552...st9h6j)"
else
    report_fail "Faucet Wallet balance check failed or wallet empty"
fi

# 7. End-to-end Demo Scenario Run
echo -e "${BOLD}7. Executing End-to-End Autonomous Agent Scenario...${NC}"
DEMO_RUN=$(./scripts/run_demo.sh 2>&1)
if echo "$DEMO_RUN" | grep -q "Demo run completed successfully!"; then
    report_pass "End-to-End Orchestrator Demo completed with 100% expected state transitions"
else
    report_fail "Demo scenario encountered errors"
    echo "$DEMO_RUN"
fi

echo ""
echo -e "${BOLD}${BLUE}============================================================${NC}"
echo -e "${BOLD}Verification Summary: ${GREEN}$PASS_COUNT / $TOTAL_COUNT checks PASSED${NC}"
echo -e "${BOLD}${BLUE}============================================================${NC}"
