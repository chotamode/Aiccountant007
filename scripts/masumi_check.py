#!/usr/bin/env python3
"""Diagnostic and health check script for Masumi Payment Service and hot wallets.

Probes:
  1. Node /health
  2. Configured payment sources (V1/V2 contract addresses, policy IDs)
  3. Hot wallets (Purchasing & Selling wallets, addresses, vkeys)
  4. Wallet balances on-chain
  5. Masumi agent registry entries on Cardano Preprod
  6. Local/remote seller availability endpoints
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


def _get_env_file_val(key: str) -> str:
    if not os.path.exists(".env"):
        return ""
    try:
        with open(".env", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip("'\"\r ")
    except OSError:
        pass
    return ""


def get_token(explicit_token: str | None) -> str:
    if explicit_token:
        return explicit_token
    resolved_tok = os.environ.get("PAYMENT_API_KEY") or os.environ.get("ADMIN_KEY")
    if not resolved_tok:
        resolved_tok = _get_env_file_val("ADMIN_KEY") or _get_env_file_val("PAYMENT_API_KEY")
    return resolved_tok or ""


def get_base_url(explicit_url: str | None) -> str:
    if explicit_url:
        return explicit_url.rstrip("/")
    url = os.environ.get("PAYMENT_SERVICE_URL") or _get_env_file_val("PAYMENT_SERVICE_URL")
    return (url or "http://127.0.0.1:3001/api/v1").rstrip("/")


def request_json(url: str, token: str = "") -> tuple[int, Any]:
    headers = {"Accept": "application/json"}
    if token:
        headers["token"] = token
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            data = json.loads(resp.read().decode())
            return resp.status, data
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return e.code, {"error": body}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, {"error": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Masumi Payment Node, Wallets, and Registry")
    parser.add_argument("--url", help="Payment service base URL (e.g. http://127.0.0.1:3001/api/v1)")
    parser.add_argument("--token", help="Admin or Payment API token")
    parser.add_argument("--network", default="Preprod", help="Cardano network (default: Preprod)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON summary")
    args = parser.parse_args()

    base_url = get_base_url(args.url)
    token = get_token(args.token)
    network = args.network

    results: dict[str, Any] = {
        "base_url": base_url,
        "network": network,
        "token_configured": bool(token),
        "checks": {},
    }

    if not args.json:
        print("=" * 60)
        print("🔍 Masumi Node & Cardano Preprod Diagnostics")
        print("=" * 60)
        print(f"Target URL: {base_url}")
        print(f"Network:    {network}")
        print(f"Auth Token: {'configured (' + token[-4:] + ')' if len(token) >= 4 else 'not configured'}")
        print("-" * 60)

    # 1. Health
    status, health_data = request_json(f"{base_url}/health")
    node_ok = status == 200 and health_data.get("status") == "success"
    results["checks"]["health"] = {
        "status": status,
        "ok": node_ok,
        "data": health_data,
    }

    if not args.json:
        if node_ok:
            print("✅ 1. Masumi Node Health: ONLINE (200 OK)")
        else:
            print(f"❌ 1. Masumi Node Health: FAILED ({status} - {health_data})")

    if not node_ok:
        if args.json:
            print(json.dumps(results, indent=2))
        return 1

    # 2. Payment Sources
    ps_status, ps_data = request_json(f"{base_url}/payment-source", token=token)
    payment_sources = ps_data.get("data", {}).get("PaymentSources", []) if ps_status == 200 else []
    results["checks"]["payment_sources"] = {
        "status": ps_status,
        "sources": payment_sources,
    }

    if not args.json:
        if ps_status == 200 and payment_sources:
            print(f"✅ 2. Payment Sources: {len(payment_sources)} source(s) configured")
            for ps in payment_sources:
                print(f"   • Type:    {ps.get('paymentSourceType')} ({ps.get('network')})")
                print(f"   • Address: {ps.get('smartContractAddress')}")
                print(f"   • Policy:  {ps.get('policyId')}")
        else:
            print(f"⚠️  2. Payment Sources: None returned or error ({ps_status})")

    # 3. Hot Wallets
    w_status, w_data = request_json(f"{base_url}/wallet/list", token=token)
    wallets = w_data.get("data", {}).get("Wallets", []) if w_status == 200 else []
    results["checks"]["wallets"] = {
        "status": w_status,
        "wallets": wallets,
    }

    if not args.json:
        if w_status == 200 and wallets:
            print(f"✅ 3. Hot Wallets: {len(wallets)} wallet(s) found")
            for w in wallets:
                w_type = w.get("type")
                w_addr = w.get("walletAddress")
                w_vkey = w.get("walletVkey")
                print(f"   • [{w_type}] Address: {w_addr}")
                print(f"              VKey:    {w_vkey}")

                # Check on-chain balance for each wallet
                b_status, b_data = request_json(f"{base_url}/balance?network={network}&address={w_addr}", token=token)
                balances = b_data.get("data", {}).get("Balance", []) if b_status == 200 else []
                total_lovelace = 0
                for item in balances:
                    if item.get("unit") in ("", "lovelace"):
                        total_lovelace = int(item.get("quantity", 0))
                ada = total_lovelace / 1_000_000
                print(f"              Balance: {ada:.2f} tADA ({total_lovelace} lovelace)")
        else:
            print(f"⚠️  3. Hot Wallets: Unable to fetch wallet list ({w_status})")

    # 4. Registry entries
    reg_status, reg_data = request_json(f"{base_url}/registry?network={network}", token=token)
    assets = reg_data.get("data", {}).get("Assets", []) if reg_status == 200 else []
    results["checks"]["registry"] = {
        "status": reg_status,
        "asset_count": len(assets),
        "assets": assets,
    }

    if not args.json:
        if reg_status == 200:
            print(f"✅ 4. On-Chain Registry: {len(assets)} registered agent(s) found on {network}")
            for a in assets:
                print(f"   • Agent:      {a.get('name')} (ID: {a.get('agentIdentifier')})")
                print(f"     API URL:    {a.get('apiBaseUrl')}")
                print(f"     State:      {a.get('state')}")
        else:
            print(f"⚠️  4. On-Chain Registry: Query error ({reg_status})")

    # 5. Seller Service Endpoints
    honest_urls = [
        os.environ.get("SELLER_HONEST_URL", ""),
        "http://127.0.0.1:8001/availability",
        "https://proucetni.tzhk.dev/availability",
    ]
    sloppy_urls = [
        os.environ.get("SELLER_SLOPPY_URL", ""),
        "http://127.0.0.1:8002/availability",
        "https://cheapbooks.tzhk.dev/availability",
    ]

    h_status, h_data, h_url = 0, {}, ""
    for u in filter(None, honest_urls):
        h_status, h_data = request_json(u)
        if h_status == 200:
            h_url = u
            break
        if not h_url:
            h_url = u

    s_status, s_data, s_url = 0, {}, ""
    for u in filter(None, sloppy_urls):
        s_status, s_data = request_json(u)
        if s_status == 200:
            s_url = u
            break
        if not s_url:
            s_url = u

    results["checks"]["sellers"] = {
        "honest": {"status": h_status, "url": h_url, "data": h_data},
        "sloppy": {"status": s_status, "url": s_url, "data": s_data},
    }

    if not args.json:
        print("-" * 60)
        h_ok = h_status == 200 and h_data.get("status") == "available"
        s_ok = s_status == 200 and s_data.get("status") == "available"
        print(f"5. Seller Honest ({h_url}): {'ONLINE' if h_ok else 'OFFLINE'} ({h_status})")
        print(f"   Seller Sloppy ({s_url}): {'ONLINE' if s_ok else 'OFFLINE'} ({s_status})")
        print("=" * 60)

    if args.json:
        print(json.dumps(results, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
