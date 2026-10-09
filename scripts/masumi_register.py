#!/usr/bin/env python3
"""Register Aiccountant007 Seller Agents on Cardano Preprod via Masumi Node.

Performs:
  1. Validates node health & payment source (Web3CardanoV2)
  2. Resolves selling wallet (vkey b1b54339...)
  3. Prepares MIP-003 compliant registration payload
  4. Submits POST /api/v1/registry to mint on-chain agent NFT
  5. Optionally polls until transaction is confirmed and outputs AGENT_IDENTIFIER
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

SELLING_VKEY_DEFAULT = "b1b54339786ea4d43e2c73b78d3d1371ed560cddbc94e72ccbbfa6a5"
V2_CONTRACT_DEFAULT = "addr_test1wzs4e6wc95hkwezlccjw9mdvq0r0rsgx6zk34avptga3ftgn37w4g"


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


def get_token(explicit: str | None) -> str:
    resolved_tok = explicit or os.environ.get("PAYMENT_API_KEY") or os.environ.get("ADMIN_KEY")
    if not resolved_tok:
        resolved_tok = _get_env_file_val("ADMIN_KEY") or _get_env_file_val("PAYMENT_API_KEY")
    return resolved_tok or ""


def get_base_url(explicit: str | None) -> str:
    url = explicit or os.environ.get("PAYMENT_SERVICE_URL") or _get_env_file_val("PAYMENT_SERVICE_URL")
    return (url or "http://127.0.0.1:3001/api/v1").rstrip("/")


def request_json(url: str, method: str = "GET", data: dict[str, Any] | None = None, token: str = "") -> tuple[int, Any]:
    headers = {"Accept": "application/json"}
    body_bytes = None
    if token:
        headers["token"] = token
    if data is not None:
        headers["Content-Type"] = "application/json"
        body_bytes = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return e.code, {"error": body}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, {"error": str(e)}


def build_payload(
    profile: str,
    network: str,
    selling_vkey: str,
    contract_address: str,
    base_url: str,
) -> dict[str, Any]:
    if profile == "honest":
        name = "ProÚčetní s.r.o. Forensic Accounting"
        desc = "Autonomous Czech VAT and ARES invoice extraction and auditing agent on Cardano Preprod"
        price_lovelace = "5000000"  # 5 tADA
        api_url = base_url or "https://proucetni.tzhk.dev"
    else:
        name = "CheapBooks s.r.o. Budget Accounting"
        desc = "High-volume budget invoice digitization service on Cardano Preprod"
        price_lovelace = "2000000"  # 2 tADA
        api_url = base_url or "https://cheapbooks.tzhk.dev"

    return {
        "network": network,
        "sellingWalletVkey": selling_vkey,
        "name": name,
        "description": desc,
        "apiBaseUrl": api_url,
        "Capability": {
            "name": "DeepSeek-V3-VAT-Audit",
            "version": "1.0.0",
        },
        "Author": {
            "name": "Aiccountant007 Team",
            "contactEmail": "agent@aiccountant007.tzhk.dev",
            "organization": "Aiccountant007 Forensic Autonomous Systems",
        },
        "Tags": ["accounting", "audit", "forensics", "vat", "czech", "isdoc"],
        "ExampleOutputs": [
            {
                "name": "audit_report_example",
                "url": f"{api_url}/availability",
                "mimeType": "application/json",
            }
        ],
        "supportedPaymentSources": [
            {
                "chain": "Cardano",
                "network": network,
                "paymentSourceType": "Web3CardanoV2",
                "address": contract_address,
                "pricing": {
                    "pricingType": "Fixed",
                    "fixed": [
                        {
                            "asset": "",
                            "amount": price_lovelace,
                        }
                    ],
                },
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Register Seller Agent on Masumi Cardano Preprod Registry")
    parser.add_argument("--profile", choices=["honest", "sloppy"], default="honest", help="Seller profile to register")
    parser.add_argument("--url", help="Payment service base URL")
    parser.add_argument("--token", help="Admin/Payment token")
    parser.add_argument("--network", default="Preprod", help="Cardano network")
    parser.add_argument("--api-base-url", help="Public HTTPS base URL for agent")
    parser.add_argument("--selling-vkey", default=SELLING_VKEY_DEFAULT, help="Selling wallet payment key hash")
    parser.add_argument("--contract-address", default=V2_CONTRACT_DEFAULT, help="Web3CardanoV2 contract address")
    parser.add_argument("--confirm", action="store_true", help="Confirm execution (submits POST to node)")
    parser.add_argument("--wait", action="store_true", help="Wait for on-chain minting confirmation")
    args = parser.parse_args()

    node_url = get_base_url(args.url)
    token = get_token(args.token)

    if not token:
        print("❌ Error: No auth token found. Specify --token or set ADMIN_KEY / PAYMENT_API_KEY in .env")
        return 1

    payload = build_payload(
        profile=args.profile,
        network=args.network,
        selling_vkey=args.selling_vkey,
        contract_address=args.contract_address,
        base_url=args.api_base_url or "",
    )

    print("=" * 60)
    print(f"📋 Masumi Agent Registration Preview ({args.profile.upper()})")
    print("=" * 60)
    print(f"Target Node:       {node_url}")
    print(f"Agent Name:        {payload['name']}")
    print(f"Public API URL:    {payload['apiBaseUrl']}")
    print(f"Selling VKey:      {payload['sellingWalletVkey']}")
    print(f"Contract Address:  {payload['supportedPaymentSources'][0]['address']}")
    print(f"Pricing:           {int(payload['supportedPaymentSources'][0]['pricing']['fixed'][0]['amount']) / 1_000_000:.2f} tADA")
    print("-" * 60)
    print("JSON Payload:")
    print(json.dumps(payload, indent=2))
    print("=" * 60)

    if not args.confirm:
        print("\n⚠️  Dry run mode. To register on Cardano Preprod, run with --confirm:")
        print(f"   python3 scripts/masumi_register.py --profile {args.profile} --confirm")
        return 0

    print("\n🚀 Submitting registration to Masumi node...")
    status, response = request_json(f"{node_url}/registry", method="POST", data=payload, token=token)

    if status not in (200, 201):
        print(f"❌ Registration request failed (HTTP {status}):")
        print(json.dumps(response, indent=2))
        return 1

    req_data = response.get("data", {})
    req_id = req_data.get("id")
    state = req_data.get("state")
    agent_id = req_data.get("agentIdentifier")

    print("✅ Registration request submitted successfully!")
    print(f"   Request ID:       {req_id}")
    print(f"   State:            {state}")
    if agent_id:
        print(f"   Agent Identifier: {agent_id}")

    if not args.wait:
        print("\n💡 The Masumi node worker will mint the registration NFT on Cardano Preprod.")
        print("   Use `python3 scripts/masumi_check.py` to monitor status.")
        if agent_id:
            env_var = "AGENT_IDENTIFIER_HONEST" if args.profile == "honest" else "AGENT_IDENTIFIER_SLOPPY"
            print(f"   Add to your .env: {env_var}={agent_id}")
        return 0

    print("\n⏳ Polling for on-chain registration confirmation...")
    start_time = time.time()
    while time.time() - start_time < 300:
        time.sleep(10)
        r_status, r_data = request_json(f"{node_url}/registry?network={args.network}", token=token)
        if r_status != 200:
            continue
        assets = r_data.get("data", {}).get("Assets", [])
        for asset in assets:
            if asset.get("id") == req_id or asset.get("name") == payload["name"]:
                cur_state = asset.get("state")
                cur_id = asset.get("agentIdentifier")
                print(f"   Status update: {cur_state} | identifier: {cur_id}")
                if cur_id and cur_state == "Registered":
                    print("\n🎉 AGENT SUCCESSFULLY REGISTERED ON-CHAIN!")
                    print(f"   Agent Identifier: {cur_id}")
                    env_var = "AGENT_IDENTIFIER_HONEST" if args.profile == "honest" else "AGENT_IDENTIFIER_SLOPPY"
                    print(f"   Set in .env: {env_var}={cur_id}")
                    return 0
                if cur_state == "Failed":
                    print(f"❌ Registration failed on-chain: {asset.get('error')}")
                    return 1

    print("⚠️ Timeout waiting for on-chain confirmation (will continue in background on node).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
