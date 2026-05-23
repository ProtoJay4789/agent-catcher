#!/usr/bin/env python3
"""
Rugcheck Agent Loop — Continuous Token Monitoring
===================================================
Autonomous agent that scans Bags.fm for new token launches,
scores them for risk, and alerts on HIGH/CRITICAL tokens.

Usage:
    python3 agent_loop.py                    # Run with defaults
    python3 agent_loop.py --interval 30      # Scan every 30 seconds
    python3 agent_loop.py --webhook <url>    # Send alerts to webhook
    python3 agent_loop.py --telegram         # Send alerts to Telegram
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Set

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bags_scanner import (
    BagsClient,
    SolanaClient,
    extract_solana_risk_factors,
    calculate_risk_score,
    send_alert,
    print_results,
)


# ─── Configuration ────────────────────────────────────────────────────────────

DEFAULT_INTERVAL = 60  # seconds between scans
ALERT_THRESHOLD = "HIGH"  # alert on HIGH or CRITICAL
LOG_FILE = "rugcheck_log.json"


# ─── Agent State ──────────────────────────────────────────────────────────────

class AgentState:
    """Track agent state across scans."""
    
    def __init__(self):
        self.scanned_tokens: Set[str] = set()
        self.scan_count: int = 0
        self.alert_count: int = 0
        self.start_time: float = time.time()
        self.risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    
    def record_scan(self, mint: str, level: str):
        """Record a token scan."""
        self.scanned_tokens.add(mint)
        self.scan_count += 1
        self.risk_counts[level] = self.risk_counts.get(level, 0) + 1
    
    def record_alert(self):
        """Record an alert sent."""
        self.alert_count += 1
    
    def get_stats(self) -> Dict:
        """Get current stats."""
        uptime = time.time() - self.start_time
        return {
            "uptime_seconds": int(uptime),
            "uptime_formatted": self._format_uptime(uptime),
            "total_scans": self.scan_count,
            "unique_tokens": len(self.scanned_tokens),
            "alerts_sent": self.alert_count,
            "risk_distribution": self.risk_counts.copy(),
        }
    
    def _format_uptime(self, seconds: float) -> str:
        """Format uptime as human-readable string."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"


# ─── Agent Loop ───────────────────────────────────────────────────────────────

def run_agent_loop(interval: int = DEFAULT_INTERVAL, webhook_url: str = "",
                   use_telegram: bool = False, simulate: bool = False):
    """Main agent loop — scan, score, alert."""
    
    print()
    print("🛡️  Rugcheck Agent — Starting Up")
    print("=" * 60)
    print(f"  Interval:   {interval}s")
    print(f"  Mode:       {'SIMULATION' if simulate else 'LIVE'}")
    print(f"  Webhook:    {'Yes' if webhook_url else 'No'}")
    print(f"  Telegram:   {'Yes' if use_telegram else 'No'}")
    print("=" * 60)
    print()
    
    state = AgentState()
    bags = BagsClient()
    
    try:
        while True:
            state.scan_count += 1
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            print(f"\n[{timestamp}] Scan #{state.scan_count}")
            print("-" * 40)
            
            # Get recent launches
            if simulate:
                # Generate mock data for demo
                launches = _generate_mock_launches()
            else:
                launches = bags.get_recent_launches(limit=10)
            
            if not launches:
                print("  No new tokens found.")
            else:
                for token in launches:
                    mint = token.get("mint", "")
                    
                    # Skip already scanned
                    if mint in state.scanned_tokens:
                        continue
                    
                    # Get detailed data
                    if simulate:
                        token_data, holders, lp_data = _simulate_token_data(mint)
                    else:
                        token_data = bags.get_token_info(mint)
                        holders = bags.get_token_holders(mint)
                        lp_data = bags.get_token_lp_info(mint)
                    
                    # Score it
                    factors = extract_solana_risk_factors(token_data, holders, lp_data)
                    score, penalty, level = calculate_risk_score(factors)
                    
                    # Record
                    state.record_scan(mint, level)
                    
                    # Output
                    print_results(mint, token_data, holders, lp_data, 
                                 factors, score, penalty, level, simulate)
                    
                    # Alert if risky
                    if level in ("HIGH", "CRITICAL"):
                        send_alert(mint, token_data, score, level, factors, webhook_url)
                        state.record_alert()
                        
                        # Telegram alert if configured
                        if use_telegram:
                            _send_telegram_alert(mint, token_data, score, level, factors)
            
            # Print stats
            stats = state.get_stats()
            print(f"\n📊 Stats: {stats['unique_tokens']} tokens scanned | "
                  f"{stats['alerts_sent']} alerts sent | "
                  f"Uptime: {stats['uptime_formatted']}")
            
            # Wait for next scan
            print(f"\n⏳ Next scan in {interval}s...")
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\n👋 Agent stopped.")
        stats = state.get_stats()
        print(f"\n📊 Final Stats:")
        print(f"  Total scans:    {stats['total_scans']}")
        print(f"  Unique tokens:  {stats['unique_tokens']}")
        print(f"  Alerts sent:    {stats['alerts_sent']}")
        print(f"  Risk breakdown: {stats['risk_distribution']}")
        print(f"  Uptime:         {stats['uptime_formatted']}")


def _generate_mock_launches() -> List[Dict]:
    """Generate mock token launches for demo."""
    import random
    
    tokens = [
        {"mint": f"0x{random.randint(1000, 9999):04x}...{random.randint(1000, 9999):04x}",
         "name": random.choice(["MoonShot", "SafeToken", "RugPull", "Diamond", "ScamCoin"]),
         "symbol": random.choice(["MOON", "SAFE", "RUG", "DIAM", "SCAM"])}
        for _ in range(random.randint(1, 5))
    ]
    return tokens


def _simulate_token_data(mint: str):
    """Generate simulated token data."""
    import random
    
    scenario = random.choice(["safe", "suspicious", "dangerous", "mixed"])
    
    if scenario == "safe":
        token_data = {
            "mint": mint, "name": "SafeToken", "symbol": "SAFE",
            "mintAuthority": None, "freezeAuthority": None,
            "holderCount": 12500, "createdAt": time.time() - 86400 * 30,
            "creatorRevealed": True, "flagged": False, "verified": True,
            "social": {"website": "https://safe.io", "twitter": "@safe"},
        }
        holders = [{"address": "0x0001", "percentage": 5.0}]
        lp_data = {"totalValueLocked": 250000, "isLocked": True}
    elif scenario == "dangerous":
        token_data = {
            "mint": mint, "name": "ScamCoin", "symbol": "SCAM",
            "mintAuthority": "0xdead", "freezeAuthority": "0xdead",
            "holderCount": 15, "createdAt": time.time() - 3600,
            "creatorRevealed": False, "flagged": True, "verified": False,
            "social": {},
        }
        holders = [{"address": "0xdead", "percentage": 85.0}]
        lp_data = {"totalValueLocked": 500, "isLocked": False}
    else:
        token_data = {
            "mint": mint, "name": "MixedToken", "symbol": "MIX",
            "mintAuthority": "0x1234", "freezeAuthority": None,
            "holderCount": 4800, "createdAt": time.time() - 86400 * 14,
            "creatorRevealed": True, "flagged": False, "verified": True,
            "social": {"website": "https://mix.io"},
        }
        holders = [{"address": "0x1234", "percentage": 22.0}]
        lp_data = {"totalValueLocked": 45000, "isLocked": True}
    
    return token_data, holders, lp_data


def _send_telegram_alert(mint: str, token_data: Dict, score: int, level: str,
                         factors: Dict[str, bool]):
    """Send alert to Telegram (placeholder)."""
    # In production, this would use the Telegram Bot API
    name = token_data.get("name", "Unknown")
    symbol = token_data.get("symbol", "???")
    risk_flags = [k for k, v in factors.items() if v]
    
    msg = f"""
🚨 RUGCHECK ALERT — {level} RISK

Token: {name} ({symbol})
Mint: {mint}
Score: {score}/100

Risk Factors:
{chr(10).join(f'  • {f}' for f in risk_flags)}

⚠️  DO NOT APE IN!
"""
    print(f"\n📱 Telegram Alert:\n{msg}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rugcheck-agent",
        description="🛡️  Rugcheck Agent — Continuous Token Monitoring",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Run with defaults (60s interval)
  %(prog)s --interval 30            # Scan every 30 seconds
  %(prog)s --simulate               # Use simulated data
  %(prog)s --webhook <url>          # Send alerts to webhook
  %(prog)s --telegram               # Send alerts to Telegram
        """,
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"Seconds between scans (default: {DEFAULT_INTERVAL})",
    )
    parser.add_argument(
        "--webhook", "-w",
        help="Webhook URL for alerts",
    )
    parser.add_argument(
        "--telegram", "-t",
        action="store_true",
        help="Send alerts to Telegram",
    )
    parser.add_argument(
        "--simulate", "-s",
        action="store_true",
        help="Use simulated data instead of live API",
    )
    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    
    run_agent_loop(
        interval=args.interval,
        webhook_url=args.webhook or "",
        use_telegram=args.telegram,
        simulate=args.simulate,
    )
