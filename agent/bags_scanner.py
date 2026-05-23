#!/usr/bin/env python3
"""
Bags.fm API Client — Token Scanner
===================================
Scans new token launches on Bags.fm using their REST API.
Part of the Bags Hackathon 2026 submission "Rugcheck for Bags".

Usage:
    python3 bags_scanner.py --scan
    python3 bags_scanner.py --token <mint_address>
    python3 bags_scanner.py --live  # continuous scanning
"""

import argparse
import json
import os
import sys
import time
from typing import Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    print("❌ 'requests' library not found. Install with: pip install requests")
    sys.exit(1)


# ─── Constants ────────────────────────────────────────────────────────────────

BAGS_API_BASE = "https://api.bags.fm"
BAGS_API_KEY = os.environ.get("BAGS_API_KEY", "")

# Solana RPC for on-chain data
SOLANA_RPC = os.environ.get("SOLANA_RPC", "https://api.mainnet-beta.solana.com")

# Risk factor weights for Solana/Bags tokens (total = 1.0)
RISK_WEIGHTS = {
    "mint_authority_active":     0.18,  # Can supply be inflated?
    "freeze_authority_active":   0.15,  # Can trades be frozen?
    "low_liquidity":            0.12,  # LP < threshold
    "lp_not_locked":            0.10,  # Liquidity not locked
    "high_concentration":       0.10,  # Top holder > 30%
    "no_social_presence":       0.08,  # No website/social
    "recent_creation":          0.07,  # Created < 24h ago
    "hidden_owner":             0.08,  # Owner not revealed
    "malicious_behavior":       0.05,  # Known scam patterns
    "low_holder_count":         0.04,  # < 100 holders
    "no_contract_verified":     0.03,  # Contract not verified
}

# Thresholds for classification
RISK_THRESHOLDS = {
    "LOW":      (80, 100),
    "MEDIUM":   (60, 79),
    "HIGH":     (40, 59),
    "CRITICAL": (0, 39),
}


# ─── Bags API Client ─────────────────────────────────────────────────────────

class BagsClient:
    """Client for Bags.fm REST API."""
    
    def __init__(self, api_key: str = ""):
        self.api_key = api_key or BAGS_API_KEY
        self.base_url = BAGS_API_BASE
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        } if self.api_key else {}
    
    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        """Make a GET request to Bags API."""
        url = f"{self.base_url}{endpoint}"
        try:
            resp = requests.get(url, headers=self.headers, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Bags API error: {e}")
            return {}
    
    def _post(self, endpoint: str, data: Dict = None) -> Dict:
        """Make a POST request to Bags API."""
        url = f"{self.base_url}{endpoint}"
        try:
            resp = requests.post(url, headers=self.headers, json=data, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Bags API error: {e}")
            return {}
    
    def get_recent_launches(self, limit: int = 10) -> List[Dict]:
        """Fetch recent token launches from Bags."""
        # Bags API endpoint for recent launches
        data = self._get("/v1/tokens/recent", {"limit": limit})
        return data.get("tokens", [])
    
    def get_token_info(self, mint_address: str) -> Dict:
        """Get detailed info for a specific token."""
        return self._get(f"/v1/tokens/{mint_address}")
    
    def get_token_holders(self, mint_address: str) -> List[Dict]:
        """Get top holders for a token."""
        data = self._get(f"/v1/tokens/{mint_address}/holders")
        return data.get("holders", [])
    
    def get_token_lp_info(self, mint_address: str) -> Dict:
        """Get liquidity pool info for a token."""
        return self._get(f"/v1/tokens/{mint_address}/lp")


# ─── Solana RPC Client ───────────────────────────────────────────────────────

class SolanaClient:
    """Client for Solana RPC calls."""
    
    def __init__(self, rpc_url: str = ""):
        self.rpc_url = rpc_url or SOLANA_RPC
    
    def _post(self, method: str, params: list = None) -> Dict:
        """Make a JSON-RPC call to Solana."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or [],
        }
        try:
            resp = requests.post(self.rpc_url, json=payload, timeout=15)
            resp.raise_for_status()
            return resp.json().get("result", {})
        except Exception as e:
            print(f"❌ Solana RPC error: {e}")
            return {}
    
    def get_token_supply(self, mint_address: str) -> Dict:
        """Get token supply info."""
        return self._post("getTokenSupply", [mint_address])
    
    def get_account_info(self, address: str) -> Dict:
        """Get account info."""
        return self._post("getAccountInfo", [address, {"encoding": "jsonParsed"}])
    
    def get_recent_blockhash(self) -> str:
        """Get recent blockhash."""
        result = self._post("getRecentBlockhash")
        return result.get("blockhash", "")


# ─── Risk Scoring Engine ──────────────────────────────────────────────────────

def extract_solana_risk_factors(token_data: Dict, holders: List[Dict], 
                                 lp_data: Dict) -> Dict[str, bool]:
    """Extract boolean risk factors from Bags + Solana data."""
    factors = {}
    
    # Mint authority — can supply be inflated?
    factors["mint_authority_active"] = token_data.get("mintAuthority") is not None
    
    # Freeze authority — can trades be frozen?
    factors["freeze_authority_active"] = token_data.get("freezeAuthority") is not None
    
    # Low liquidity — LP < $10K
    lp_value = lp_data.get("totalValueLocked", 0)
    factors["low_liquidity"] = lp_value < 10000
    
    # LP not locked — no lock expiry or lock info
    factors["lp_not_locked"] = not lp_data.get("isLocked", False)
    
    # High concentration — top holder > 30%
    if holders:
        top_holder_pct = holders[0].get("percentage", 0)
        factors["high_concentration"] = top_holder_pct > 30
    else:
        factors["high_concentration"] = False
    
    # No social presence
    social = token_data.get("social", {})
    factors["no_social_presence"] = not any([
        social.get("website"),
        social.get("twitter"),
        social.get("telegram"),
    ])
    
    # Recent creation — < 24 hours
    created_at = token_data.get("createdAt", 0)
    factors["recent_creation"] = (time.time() - created_at) < 86400
    
    # Hidden owner — creator not revealed
    factors["hidden_owner"] = not token_data.get("creatorRevealed", False)
    
    # Malicious behavior — known scam patterns
    factors["malicious_behavior"] = token_data.get("flagged", False)
    
    # Low holder count — < 100
    holder_count = token_data.get("holderCount", 0)
    factors["low_holder_count"] = holder_count < 100
    
    # No contract verified
    factors["no_contract_verified"] = not token_data.get("verified", False)
    
    return factors


def calculate_risk_score(factors: Dict[str, bool]) -> Tuple[int, float, str]:
    """
    Calculate a risk score from 0 (worst) to 100 (safest).
    Returns (score, penalty_breakdown, level).
    """
    total_penalty = 0.0
    
    for factor, weight in RISK_WEIGHTS.items():
        is_risky = factors.get(factor, False)
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


# ─── Simulation Mode ─────────────────────────────────────────────────────────

def simulate_token_data(mint_address: str = "") -> Tuple[Dict, List[Dict], Dict]:
    """Generate realistic fake token data for demo purposes."""
    import random
    
    scenario = random.choice(["safe", "suspicious", "dangerous", "mixed"])
    
    if scenario == "safe":
        token_data = {
            "mint": mint_address or "So11111111111111111111111111111111",
            "name": "SafeToken",
            "symbol": "SAFE",
            "mintAuthority": None,
            "freezeAuthority": None,
            "holderCount": 12500,
            "createdAt": time.time() - 86400 * 30,
            "creatorRevealed": True,
            "flagged": False,
            "verified": True,
            "social": {
                "website": "https://safetoken.io",
                "twitter": "@safetoken",
                "telegram": "t.me/safetoken",
            },
        }
        holders = [
            {"address": "0x0000...0001", "percentage": 5.2},
            {"address": "0x0000...0002", "percentage": 3.1},
            {"address": "0x0000...0003", "percentage": 2.8},
        ]
        lp_data = {"totalValueLocked": 250000, "isLocked": True}
        
    elif scenario == "suspicious":
        token_data = {
            "mint": mint_address or "0x0000...suspicious",
            "name": "SuspiciousToken",
            "symbol": "SUSP",
            "mintAuthority": "0x1234...5678",
            "freezeAuthority": None,
            "holderCount": 320,
            "createdAt": time.time() - 86400 * 3,
            "creatorRevealed": False,
            "flagged": False,
            "verified": False,
            "social": {
                "website": None,
                "twitter": "@suspicious",
                "telegram": None,
            },
        }
        holders = [
            {"address": "0x1234...5678", "percentage": 45.0},
            {"address": "0x0000...0002", "percentage": 8.2},
            {"address": "0x0000...0003", "percentage": 5.1},
        ]
        lp_data = {"totalValueLocked": 8500, "isLocked": False}
        
    elif scenario == "dangerous":
        token_data = {
            "mint": mint_address or "0x0000...scam",
            "name": "ScamCoin",
            "symbol": "SCAM",
            "mintAuthority": "0xdead...beef",
            "freezeAuthority": "0xdead...beef",
            "holderCount": 15,
            "createdAt": time.time() - 3600,
            "creatorRevealed": False,
            "flagged": True,
            "verified": False,
            "social": {},
        }
        holders = [
            {"address": "0xdead...beef", "percentage": 85.0},
            {"address": "0x0000...0002", "percentage": 2.1},
        ]
        lp_data = {"totalValueLocked": 500, "isLocked": False}
        
    else:  # mixed
        token_data = {
            "mint": mint_address or "0x0000...mixed",
            "name": "MixedToken",
            "symbol": "MIX",
            "mintAuthority": "0x1234...5678",
            "freezeAuthority": None,
            "holderCount": 4800,
            "createdAt": time.time() - 86400 * 14,
            "creatorRevealed": True,
            "flagged": False,
            "verified": True,
            "social": {
                "website": "https://mixedtoken.io",
                "twitter": None,
                "telegram": "t.me/mixedtoken",
            },
        }
        holders = [
            {"address": "0x1234...5678", "percentage": 22.0},
            {"address": "0x0000...0002", "percentage": 12.5},
            {"address": "0x0000...0003", "percentage": 8.3},
        ]
        lp_data = {"totalValueLocked": 45000, "isLocked": True}
    
    return token_data, holders, lp_data


# ─── Pretty Printer ───────────────────────────────────────────────────────────

def _flag(val: bool) -> str:
    return "🔴 YES" if val else "🟢 NO"

def _level_badge(level: str) -> str:
    badges = {
        "LOW":      "🟢 LOW",
        "MEDIUM":   "🟡 MEDIUM",
        "HIGH":     "🟠 HIGH",
        "CRITICAL": "🔴 CRITICAL",
    }
    return badges.get(level, level)


def print_results(mint_address: str, token_data: Dict, holders: List[Dict],
                  lp_data: Dict, factors: Dict[str, bool], score: int, 
                  penalty: float, level: str, simulated: bool = False):
    """Pretty-print the scan results."""
    name = token_data.get("name", "N/A")
    symbol = token_data.get("symbol", "N/A")
    holders_count = token_data.get("holderCount", "N/A")
    mint_auth = "ACTIVE" if factors["mint_authority_active"] else "REVOKED"
    freeze_auth = "ACTIVE" if factors["freeze_authority_active"] else "REVOKED"
    lp_value = lp_data.get("totalValueLocked", 0)
    
    mode_tag = " [SIMULATED]" if simulated else ""
    
    print()
    print("=" * 60)
    print(f"  🛡️  Rugcheck — Bags Token Risk Report{mode_tag}")
    print("=" * 60)
    print()
    print(f"  📌 Token:     {name} ({symbol})")
    print(f"  🔑 Mint:      {mint_address}")
    print(f"  👥 Holders:   {holders_count}")
    print(f"  💰 LP Value:  ${lp_value:,.2f}")
    print(f"  🔐 Mint Auth: {mint_auth}")
    print(f"  🧊 Freeze:    {freeze_auth}")
    print()
    print("-" * 60)
    print("  📊 Risk Factors")
    print("-" * 60)
    print(f"    Mint Authority Active:   {_flag(factors['mint_authority_active'])}")
    print(f"    Freeze Authority Active: {_flag(factors['freeze_authority_active'])}")
    print(f"    Low Liquidity:           {_flag(factors['low_liquidity'])}")
    print(f"    LP Not Locked:           {_flag(factors['lp_not_locked'])}")
    print(f"    High Concentration:      {_flag(factors['high_concentration'])}")
    print(f"    No Social Presence:      {_flag(factors['no_social_presence'])}")
    print(f"    Recent Creation:         {_flag(factors['recent_creation'])}")
    print(f"    Hidden Owner:            {_flag(factors['hidden_owner'])}")
    print(f"    Malicious Behavior:      {_flag(factors['malicious_behavior'])}")
    print(f"    Low Holder Count:        {_flag(factors['low_holder_count'])}")
    print(f"    No Contract Verified:    {_flag(factors['no_contract_verified'])}")
    print()
    print("-" * 60)
    print("  🎯 Risk Assessment")
    print("-" * 60)
    print(f"    Score:     {score}/100")
    print(f"    Level:     {_level_badge(level)}")
    print(f"    Penalty:   {penalty:.1%}")
    print()
    print("=" * 60)


# ─── Alert Dispatcher ────────────────────────────────────────────────────────

def send_alert(mint_address: str, token_data: Dict, score: int, level: str,
               factors: Dict[str, bool], webhook_url: str = ""):
    """Send alert for HIGH/CRITICAL risk tokens."""
    if level not in ("HIGH", "CRITICAL"):
        return
    
    name = token_data.get("name", "Unknown")
    symbol = token_data.get("symbol", "???")
    
    # Build risk summary
    risk_flags = [k for k, v in factors.items() if v]
    
    alert_msg = f"""
🚨 RUGCHECK ALERT — {level} RISK 🚨

Token: {name} ({symbol})
Mint: {mint_address}
Score: {score}/100

Risk Factors:
{chr(10).join(f'  • {f}' for f in risk_flags)}

⚠️  DO NOT APE IN without further research!
"""
    
    print(alert_msg)
    
    # Send to webhook if configured
    if webhook_url:
        try:
            payload = {
                "text": alert_msg,
                "token": mint_address,
                "score": score,
                "level": level,
            }
            requests.post(webhook_url, json=payload, timeout=10)
        except Exception as e:
            print(f"⚠️  Webhook failed: {e}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rugcheck-bags",
        description="🛡️  Rugcheck — Bags Token Risk Scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --scan                    # Scan recent Bags launches
  %(prog)s --token <mint_address>    # Scan specific token
  %(prog)s --live                    # Continuous scanning mode
  %(prog)s --simulate                # Use simulated data
        """,
    )
    parser.add_argument(
        "--scan", "-s",
        action="store_true",
        help="Scan recent Bags token launches",
    )
    parser.add_argument(
        "--token", "-t",
        help="Scan a specific token by mint address",
    )
    parser.add_argument(
        "--live", "-l",
        action="store_true",
        help="Continuous scanning mode (polls every 60s)",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Use simulated data instead of live API",
    )
    parser.add_argument(
        "--webhook",
        help="Webhook URL for alerts",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted table",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of recent launches to scan (default: 10)",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    
    print()
    print("🛡️  Rugcheck — Bags Token Risk Scanner")
    print("=" * 60)
    
    bags = BagsClient()
    solana = SolanaClient()
    
    if args.live:
        # Continuous scanning mode
        print("  Mode: LIVE SCANNING (Ctrl+C to stop)")
        print("  Polling every 60 seconds...")
        print()
        
        seen_tokens = set()
        
        while True:
            try:
                launches = bags.get_recent_launches(limit=args.limit)
                
                for token in launches:
                    mint = token.get("mint", "")
                    if mint in seen_tokens:
                        continue
                    
                    seen_tokens.add(mint)
                    
                    # Get detailed data
                    token_data = bags.get_token_info(mint)
                    holders = bags.get_token_holders(mint)
                    lp_data = bags.get_token_lp_info(mint)
                    
                    # Score it
                    factors = extract_solana_risk_factors(token_data, holders, lp_data)
                    score, penalty, level = calculate_risk_score(factors)
                    
                    # Output
                    if args.json:
                        result = {
                            "mint": mint,
                            "name": token_data.get("name"),
                            "symbol": token_data.get("symbol"),
                            "score": score,
                            "level": level,
                            "factors": factors,
                        }
                        print(json.dumps(result))
                    else:
                        print_results(mint, token_data, holders, lp_data, 
                                     factors, score, penalty, level)
                    
                    # Alert if risky
                    send_alert(mint, token_data, score, level, factors, args.webhook)
                
                time.sleep(60)
                
            except KeyboardInterrupt:
                print("\n\n👋 Stopping live scanner...")
                break
    
    elif args.token:
        # Scan specific token
        mint = args.token
        print(f"  Target: {mint}")
        print(f"  Mode:   {'SIMULATION' if args.simulate else 'LIVE (Bags API)'}")
        print()
        
        if args.simulate:
            token_data, holders, lp_data = simulate_token_data(mint)
        else:
            token_data = bags.get_token_info(mint)
            holders = bags.get_token_holders(mint)
            lp_data = bags.get_token_lp_info(mint)
        
        factors = extract_solana_risk_factors(token_data, holders, lp_data)
        score, penalty, level = calculate_risk_score(factors)
        
        if args.json:
            result = {
                "mint": mint,
                "name": token_data.get("name"),
                "symbol": token_data.get("symbol"),
                "score": score,
                "level": level,
                "factors": factors,
            }
            print(json.dumps(result))
        else:
            print_results(mint, token_data, holders, lp_data, 
                         factors, score, penalty, level, args.simulate)
        
        send_alert(mint, token_data, score, level, factors, args.webhook)
    
    elif args.scan:
        # Scan recent launches
        print(f"  Mode: SCANNING RECENT LAUNCHES (limit: {args.limit})")
        print()
        
        launches = bags.get_recent_launches(limit=args.limit)
        
        if not launches:
            print("  No recent launches found.")
            return
        
        for token in launches:
            mint = token.get("mint", "")
            
            if args.simulate:
                token_data, holders, lp_data = simulate_token_data(mint)
            else:
                token_data = bags.get_token_info(mint)
                holders = bags.get_token_holders(mint)
                lp_data = bags.get_token_lp_info(mint)
            
            factors = extract_solana_risk_factors(token_data, holders, lp_data)
            score, penalty, level = calculate_risk_score(factors)
            
            if args.json:
                result = {
                    "mint": mint,
                    "name": token_data.get("name"),
                    "symbol": token_data.get("symbol"),
                    "score": score,
                    "level": level,
                    "factors": factors,
                }
                print(json.dumps(result))
            else:
                print_results(mint, token_data, holders, lp_data, 
                             factors, score, penalty, level, args.simulate)
            
            send_alert(mint, token_data, score, level, factors, args.webhook)
    
    else:
        # Default: scan recent launches
        parser.print_help()


if __name__ == "__main__":
    main()
