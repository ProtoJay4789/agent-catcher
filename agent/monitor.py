#!/usr/bin/env python3
"""
Agent Catcher — Token Risk Monitor
===================================
Scans Sui token addresses using GoPlus API and calculates risk scores.
Part of the Sui Overflow 2026 hackathon project "Agent Catcher".

Usage:
    python3 monitor.py --token 0x2::sui::SUI --simulate
    python3 monitor.py --token 0xtoken_address --submit
    python3 monitor.py --token 0xtoken_address          # live GoPlus scan
"""

import argparse
import json
import random
import sys
import time
from typing import Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    print("❌ 'requests' library not found. Install with: pip install requests")
    sys.exit(1)


# ─── Constants ────────────────────────────────────────────────────────────────

GOPLUS_API = "https://api.gopluslabs.io/api/v1/token_security/1"
GOPLUS_CHAIN_ID = 1  # GoPlus uses 1 for ethereum-like; Sui tokens need simulation

# On-chain registry details (Sui devnet)
PACKAGE_ID = "0x20e7a4ff0eab4f0eae72614c61022853c39368fb336b48db8e87a19284a97e43"
REGISTRY_ID = "0x7639df5cdbf75797895ef2632f0f84ed6a053be7f7ba1a3470bb1c1d33d7ebeb"
MODULE_NAME = "risk_oracle"
FUNCTION_NAME = "submit_assessment"

# Risk factor weights (total = 1.0)
RISK_WEIGHTS = {
    "is_honeypot":              0.20,
    "is_open_source":           0.10,  # negative factor (open source = good)
    "owner_change_balance":     0.10,
    "can_take_back_liquidity":  0.12,
    "hidden_owner":             0.10,
    "selfdestruct":             0.08,
    "external_call":            0.05,
    "is_proxy":                 0.05,
    "malicious_behavior":       0.10,
    "slippage_modifiable":      0.05,
    "is_blacklisted":           0.05,
}

# Thresholds for classification
RISK_THRESHOLDS = {
    "LOW":      (80, 100),
    "MEDIUM":   (60, 79),
    "HIGH":     (40, 59),
    "CRITICAL": (0, 39),
}


# ─── GoPlus Scanner ───────────────────────────────────────────────────────────

def scan_goplus(token_address: str, timeout: int = 15) -> Dict:
    """Query GoPlus API for token security data."""
    url = f"{GOPLUS_API}?contract_addresses={token_address}"
    print(f"🌐 Querying GoPlus API: {url}")

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 1:
            print(f"⚠️  GoPlus returned error: {data.get('message', 'unknown')}")
            return {}

        results = data.get("result", {}).get(token_address.lower(), {})
        if not results:
            # Try without 0x prefix or other casing
            for key, val in data.get("result", {}).items():
                if token_address.lower().endswith(key) or key.endswith(token_address.lower()):
                    results = val
                    break
        return results

    except requests.exceptions.RequestException as e:
        print(f"❌ GoPlus API request failed: {e}")
        return {}


def simulate_goplus(token_address: str) -> Dict:
    """Generate realistic fake GoPlus data for demo purposes."""
    print("🎭 Generating simulated GoPlus data...")

    # Create a mix — mostly safe with a few suspicious tokens sprinkled in
    scenario = random.choice(["safe", "suspicious", "dangerous", "mixed"])

    if scenario == "safe":
        return {
            "is_open_source": "1",
            "is_proxy": "0",
            "is_mutable_proxy": "0",
            "is_honeypot": "0",
            "owner_change_balance": "0",
            "can_take_back_liquidity": "0",
            "hidden_owner": "0",
            "selfdestruct": "0",
            "external_call": "0",
            "is_blacklisted": "0",
            "is_whitelisted": "1",
            "is_open_source": "1",
            "slippage_modifiable": "0",
            "trading_cooldown": "0",
            "cannot_buy_all": "0",
            "is_honeypot": "0",
            "balance": "0",
            "total_supply": "1000000000",
            "holder_count": "12500",
            "lp_holder_count": "45",
            "lp_total_supply": "500000",
            "is_true_token": "1",
            "malicious_behavior": "0",
            "token_name": "SafeToken",
            "token_symbol": "SAFE",
            "token_decimal": "9",
            "owner_address": "0x0000000000000000000000000000000000000000",
            "creation_time": str(int(time.time()) - 86400 * 30),
        }
    elif scenario == "suspicious":
        return {
            "is_open_source": "0",
            "is_proxy": "1",
            "is_mutable_proxy": "0",
            "is_honeypot": "0",
            "owner_change_balance": "1",
            "can_take_back_liquidity": "0",
            "hidden_owner": "1",
            "selfdestruct": "0",
            "external_call": "1",
            "is_blacklisted": "0",
            "is_whitelisted": "0",
            "slippage_modifiable": "1",
            "trading_cooldown": "0",
            "cannot_buy_all": "0",
            "is_honeypot": "0",
            "balance": "0",
            "total_supply": "500000000",
            "holder_count": "320",
            "lp_holder_count": "5",
            "lp_total_supply": "100000",
            "is_true_token": "1",
            "malicious_behavior": "0",
            "token_name": "SuspiciousToken",
            "token_symbol": "SUSP",
            "token_decimal": "9",
            "owner_address": "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            "creation_time": str(int(time.time()) - 86400 * 3),
        }
    elif scenario == "dangerous":
        return {
            "is_open_source": "0",
            "is_proxy": "1",
            "is_mutable_proxy": "1",
            "is_honeypot": "1",
            "owner_change_balance": "1",
            "can_take_back_liquidity": "1",
            "hidden_owner": "1",
            "selfdestruct": "1",
            "external_call": "1",
            "is_blacklisted": "1",
            "is_whitelisted": "0",
            "slippage_modifiable": "1",
            "trading_cooldown": "1",
            "cannot_buy_all": "1",
            "balance": "0",
            "total_supply": "666000000",
            "holder_count": "15",
            "lp_holder_count": "1",
            "lp_total_supply": "500",
            "is_true_token": "0",
            "malicious_behavior": "1",
            "token_name": "ScamCoin",
            "token_symbol": "SCAM",
            "token_decimal": "18",
            "owner_address": "0x1234567890abcdef1234567890abcdef12345678",
            "creation_time": str(int(time.time()) - 3600),
        }
    else:  # mixed
        return {
            "is_open_source": "1",
            "is_proxy": "0",
            "is_mutable_proxy": "0",
            "is_honeypot": "0",
            "owner_change_balance": "0",
            "can_take_back_liquidity": "0",
            "hidden_owner": "0",
            "selfdestruct": "0",
            "external_call": "0",
            "is_blacklisted": "0",
            "is_whitelisted": "0",
            "slippage_modifiable": "0",
            "trading_cooldown": "0",
            "cannot_buy_all": "0",
            "balance": "1000000",
            "total_supply": "200000000",
            "holder_count": "4800",
            "lp_holder_count": "22",
            "lp_total_supply": "350000",
            "is_true_token": "1",
            "malicious_behavior": "0",
            "token_name": "SuiToken",
            "token_symbol": "SUI",
            "token_decimal": "9",
            "owner_address": "0x0000000000000000000000000000000000000000",
            "creation_time": str(int(time.time()) - 86400 * 180),
        }


# ─── Risk Scoring Engine ──────────────────────────────────────────────────────

def extract_risk_factors(raw_data: Dict) -> Dict[str, bool]:
    """Extract boolean risk factors from raw GoPlus data."""
    def _bool(val):
        return str(val) == "1"

    return {
        "is_honeypot":             _bool(raw_data.get("is_honeypot", 0)),
        "is_open_source":          _bool(raw_data.get("is_open_source", 0)),
        "owner_change_balance":    _bool(raw_data.get("owner_change_balance", 0)),
        "can_take_back_liquidity": _bool(raw_data.get("can_take_back_liquidity", 0)),
        "hidden_owner":            _bool(raw_data.get("hidden_owner", 0)),
        "selfdestruct":            _bool(raw_data.get("selfdestruct", 0)),
        "external_call":           _bool(raw_data.get("external_call", 0)),
        "is_proxy":                _bool(raw_data.get("is_proxy", 0)),
        "malicious_behavior":      _bool(raw_data.get("malicious_behavior", 0)),
        "slippage_modifiable":     _bool(raw_data.get("slippage_modifiable", 0)),
        "is_blacklisted":          _bool(raw_data.get("is_blacklisted", 0)),
    }


def calculate_risk_score(factors: Dict[str, bool]) -> Tuple[int, float, str]:
    """
    Calculate a risk score from 0 (worst) to 100 (safest).
    Returns (score, penalty_breakdown, level).
    """
    total_penalty = 0.0

    for factor, weight in RISK_WEIGHTS.items():
        is_risky = factors.get(factor, False)

        # Special case: open_source is GOOD — absence is risky
        if factor == "is_open_source":
            if not is_risky:
                total_penalty += weight
        else:
            if is_risky:
                total_penalty += weight

    score = max(0, min(100, int((1.0 - total_penalty) * 100)))

    # Classify
    level = "CRITICAL"
    for lvl, (lo, hi) in RISK_THRESHOLDS.items():
        if lo <= score <= hi:
            level = lvl
            break

    return score, total_penalty, level


# ─── Pretty Printer ───────────────────────────────────────────────────────────

def _flag(val: bool) -> str:
    return "🔴 YES" if val else "🟢 NO"

def _flag_inv(val: bool) -> str:
    """For open_source: open=good, closed=bad."""
    return "🟢 YES" if val else "🔴 NO"

def _level_badge(level: str) -> str:
    badges = {
        "LOW":      "🟢 LOW",
        "MEDIUM":   "🟡 MEDIUM",
        "HIGH":     "🟠 HIGH",
        "CRITICAL": "🔴 CRITICAL",
    }
    return badges.get(level, level)


def print_results(token_address: str, raw_data: Dict, factors: Dict[str, bool],
                  score: int, penalty: float, level: str, simulated: bool = False):
    """Pretty-print the scan results."""
    name = raw_data.get("token_name", "N/A")
    symbol = raw_data.get("token_symbol", "N/A")
    holders = raw_data.get("holder_count", "N/A")
    supply = raw_data.get("total_supply", "N/A")
    owner = raw_data.get("owner_address", "N/A")

    if owner and len(owner) > 20:
        owner = owner[:10] + "..." + owner[-8:]

    mode_tag = " [SIMULATED]" if simulated else ""

    print()
    print("=" * 60)
    print(f"  🛡️  Agent Catcher — Token Risk Report{mode_tag}")
    print("=" * 60)
    print()
    print(f"  📌 Token:     {name} ({symbol})")
    print(f"  🔑 Address:   {token_address}")
    print(f"  👥 Holders:   {holders}")
    print(f"  📦 Supply:    {supply}")
    print(f"  🏷️  Owner:     {owner}")
    print()
    print("-" * 60)
    print("  📊 Risk Factors")
    print("-" * 60)
    print(f"    Honeypot:              {_flag(factors['is_honeypot'])}")
    print(f"    Open Source:           {_flag_inv(factors['is_open_source'])}")
    print(f"    Owner Can Change Bal:  {_flag(factors['owner_change_balance'])}")
    print(f"    Can Take Liquidity:    {_flag(factors['can_take_back_liquidity'])}")
    print(f"    Hidden Owner:          {_flag(factors['hidden_owner'])}")
    print(f"    Self-Destruct:         {_flag(factors['selfdestruct'])}")
    print(f"    External Call:         {_flag(factors['external_call'])}")
    print(f"    Is Proxy:              {_flag(factors['is_proxy'])}")
    print(f"    Malicious Behavior:    {_flag(factors['malicious_behavior'])}")
    print(f"    Slippage Modifiable:   {_flag(factors['slippage_modifiable'])}")
    print(f"    Blacklisted:           {_flag(factors['is_blacklisted'])}")
    print()
    print("-" * 60)
    print("  🎯 Risk Assessment")
    print("-" * 60)
    print(f"    Score:     {score}/100")
    print(f"    Level:     {_level_badge(level)}")
    print(f"    Penalty:   {penalty:.1%}")
    print()
    print("=" * 60)


# ─── On-Chain Submission Scaffold ─────────────────────────────────────────────

def scaffold_submit(token_address: str, score: int, level: str,
                    factors: Dict[str, bool], agent_id: str = "gentech_agent_v1"):
    """Scaffold the on-chain submission transaction (prints what would be sent)."""
    import base64

    timestamp = int(time.time())
    risk_factors = [k for k, v in factors.items() if v]
    # Add inverse flag
    if not factors.get("is_open_source", False):
        risk_factors.append("closed_source")

    print()
    print("-" * 60)
    print("  📤 On-Chain Submission Scaffold")
    print("-" * 60)
    print()
    print(f"  Package:     {PACKAGE_ID}")
    print(f"  Module:      {MODULE_NAME}")
    print(f"  Function:    {FUNCTION_NAME}")
    print(f"  Registry:    {REGISTRY_ID}")
    print(f"  Network:     devnet")
    print()

    # Build the transaction arguments (mirrors RiskOracleClient.submit_risk_assessment)
    arguments = [
        {"Object": {"objectId": REGISTRY_ID, "mutable": True}},
        {"Pure": list(token_address.encode())},
        {"Pure": [score]},
        {"Pure": list(level.encode())},
        {"Pure": [list(f.encode()) for f in risk_factors]},
        {"Pure": list(agent_id.encode())},
        {"Pure": [timestamp]},
    ]

    tx_kind = {
        "TransactionKind": {
            "ProgrammableTransaction": {
                "inputs": [],
                "commands": [{
                    "MoveCall": {
                        "package": PACKAGE_ID,
                        "module": MODULE_NAME,
                        "function": FUNCTION_NAME,
                        "type_arguments": [],
                        "arguments": arguments,
                    }
                }]
            }
        }
    }

    print("  Transaction payload:")
    print()

    # Indent and print the JSON nicely
    formatted = json.dumps(tx_kind, indent=4)
    for line in formatted.split("\n"):
        print(f"    {line}")

    print()
    print(f"  ⏱️  Timestamp:  {timestamp}")
    print(f"  🤖 Agent ID:   {agent_id}")
    print(f"  📋 Factors:    {risk_factors}")
    print()

    # Show base64-encoded unsigned tx
    tx_b64 = base64.b64encode(json.dumps(tx_kind).encode()).decode()
    print(f"  Unsigned TX (base64): {tx_b64[:60]}...")
    print()
    print("  ⚠️  NOTE: This is a scaffold. To actually submit:")
    print("     1. Import SuiClient from sui_client.py")
    print("     2. Sign the transaction with a private key")
    print("     3. Broadcast to Sui devnet RPC")
    print()
    print("=" * 60)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-catcher-monitor",
        description="🛡️  Agent Catcher — Token Risk Monitor (Sui Overflow 2026)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --token 0x2::sui::SUI --simulate
  %(prog)s --token 0xSomeTokenAddress --submit
  %(prog)s --token 0xtoken_address
        """,
    )
    parser.add_argument(
        "--token", "-t",
        default="0x2::sui::SUI",
        help="Token address to scan (default: 0x2::sui::SUI)",
    )
    parser.add_argument(
        "--simulate", "-s",
        action="store_true",
        help="Use simulated data instead of calling GoPlus API",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Scaffold on-chain submission after scanning",
    )
    parser.add_argument(
        "--agent-id",
        default="gentech_agent_v1",
        help="Agent identifier for on-chain records (default: gentech_agent_v1)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted table",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    token_address = args.token

    print()
    print("🛡️  Agent Catcher — Token Risk Monitor")
    print("=" * 60)
    print(f"  Target: {token_address}")
    print(f"  Mode:   {'SIMULATION' if args.simulate else 'LIVE (GoPlus)'}")
    print()

    # ── Step 1: Get raw data ──────────────────────────────────────────────
    if args.simulate:
        raw_data = simulate_goplus(token_address)
    else:
        # For Sui-native tokens (containing ::), GoPlus won't have data
        if "::" in token_address:
            print("⚠️  Sui-native tokens are not supported by GoPlus (EVM only).")
            print("    Falling back to simulation mode.")
            print()
            raw_data = simulate_goplus(token_address)
        else:
            raw_data = scan_goplus(token_address)
            if not raw_data:
                print("⚠️  No data returned. Falling back to simulation.")
                raw_data = simulate_goplus(token_address)

    # ── Step 2: Extract factors ───────────────────────────────────────────
    factors = extract_risk_factors(raw_data)

    # ── Step 3: Calculate score ───────────────────────────────────────────
    score, penalty, level = calculate_risk_score(factors)

    # ── Step 4: Output ────────────────────────────────────────────────────
    if args.json:
        output = {
            "token_address": token_address,
            "score": score,
            "level": level,
            "penalty": round(penalty, 4),
            "factors": factors,
            "raw": raw_data,
            "simulated": args.simulate or "::" in token_address,
            "timestamp": int(time.time()),
        }
        print(json.dumps(output, indent=2))
    else:
        print_results(
            token_address, raw_data, factors, score, penalty, level,
            simulated=args.simulate or "::" in token_address,
        )

    # ── Step 5: Optional on-chain submission ──────────────────────────────
    if args.submit:
        scaffold_submit(token_address, score, level, factors, args.agent_id)


if __name__ == "__main__":
    main()
