#!/usr/bin/env python3
"""
Rugcheck v2 — Autonomous Agent Loop
=====================================
Monitors new Solana token launches via Bags.fm, scores each for rug/honeypot
risk, and dispatches alerts for HIGH/CRITICAL risk tokens.

Features:
  - Polling loop with configurable interval
  - Deduplication of seen tokens
  - Graceful shutdown on SIGINT/SIGTERM
  - Optional JSON log file
  - CLI interface

Usage:
    python -m agent.agent --simulate --interval 30
    python -m agent.agent --live --api-key YOUR_KEY
"""

import argparse
import json
import logging
import signal
import sys
import time
from typing import Dict, List, Optional, Set

from .scanners.bags_client import BagsClient
from .scorer import extract_risk_factors, calculate_risk_score, print_results, RISK_WEIGHTS
from .alerts import AlertDispatcher
from .config import Config


# ─── Logger Setup ────────────────────────────────────────────────────────────

logger = logging.getLogger("rugcheck")


def setup_logging(log_file: Optional[str] = None, level: int = logging.INFO):
    """Configure logging to stdout and optionally to a JSON file."""
    logger.setLevel(level)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(console)

    # Optional file handler (JSON lines)
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(fh)


# ─── Agent Class ─────────────────────────────────────────────────────────────

class RugcheckAgent:
    """
    Autonomous token risk monitoring agent.

    Polls Bags.fm for new token launches, scores each for rug/honeypot risk,
    and dispatches alerts for HIGH/CRITICAL risk tokens.
    """

    def __init__(self, bags_client: BagsClient, alert_dispatcher: AlertDispatcher,
                 interval: int = 60, simulate: bool = True):
        """
        Initialize the Rugcheck agent.

        Args:
            bags_client: Bags.fm API client instance.
            alert_dispatcher: Alert dispatcher for sending notifications.
            interval: Seconds between scan cycles.
            simulate: Whether we're in simulation mode.
        """
        self.bags_client = bags_client
        self.alert_dispatcher = alert_dispatcher
        self.interval = interval
        self.simulate = simulate
        self._seen_tokens: Set[str] = set()
        self._running = False
        self._scan_count = 0
        self._alert_count = 0

    def scan_once(self) -> List[Dict]:
        """
        Run a single scan cycle.

        Fetches new launches, scores each, dispatches alerts for risky ones.

        Returns:
            List of result dicts for each scanned token.
        """
        self._scan_count += 1
        logger.info(f"🔍 Scan cycle #{self._scan_count} — fetching new launches...")

        results = []

        try:
            launches = self.bags_client.get_new_launches(limit=10)
        except Exception as e:
            logger.error(f"❌ Failed to fetch launches: {e}")
            return results

        if not launches:
            logger.info("  No new launches found.")
            return results

        logger.info(f"  Found {len(launches)} launches")

        for launch in launches:
            mint = launch.get("mint", "")
            if not mint:
                continue

            # Skip already-seen tokens
            if mint in self._seen_tokens:
                logger.debug(f"  ⏭️  Skipping {mint} (already seen)")
                continue

            self._seen_tokens.add(mint)
            result = self._score_and_alert(mint, launch)
            results.append(result)

        logger.info(f"  ✅ Scan complete: {len(results)} new tokens scored")
        return results

    def _score_and_alert(self, mint: str, launch_info: Dict) -> Dict:
        """
        Score a single token and dispatch alert if needed.

        Args:
            mint: Token mint address.
            launch_info: Basic launch info from get_new_launches().

        Returns:
            Result dict with score, level, and alert status.
        """
        logger.info(f"  📊 Scoring {launch_info.get('symbol', mint[:8])}...")

        # Get detailed token info
        token_info = self.bags_client.get_token_info(mint)
        if not token_info:
            token_info = launch_info  # Fallback to launch info

        # Extract risk factors
        factors = extract_risk_factors(token_info)

        # Calculate risk score
        score, penalty, level = calculate_risk_score(factors)

        # Print results
        print_results(token_info, factors, score, penalty, level, simulated=self.simulate)

        # Alert if HIGH or CRITICAL
        alert_results = []
        if self.alert_dispatcher.should_alert(level):
            alert_results = self.alert_dispatcher.send(
                mint, score, level, factors,
                agent_id="rugcheck_v2",
            )
            self._alert_count += 1

        result = {
            "mint": mint,
            "symbol": token_info.get("symbol", "N/A"),
            "score": score,
            "level": level,
            "penalty": round(penalty, 4),
            "factors": factors,
            "alerted": len(alert_results) > 0,
            "timestamp": int(time.time()),
        }

        # Log as JSON
        logger.debug(json.dumps(result))
        return result

    def run(self):
        """
        Start the main agent loop.

        Runs indefinitely until interrupted (SIGINT/SIGTERM).
        """
        self._running = True

        # Register signal handlers
        def _shutdown(sig, frame):
            logger.info(f"\n🛑 Received signal {sig}, shutting down gracefully...")
            self._running = False

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        logger.info("🛡️  Rugcheck Agent v2 — Starting")
        logger.info(f"  Mode:     {'SIMULATION' if self.simulate else 'LIVE'}")
        logger.info(f"  Interval: {self.interval}s")
        logger.info(f"  Alerts:   {self.alert_dispatcher.alert_levels}")
        logger.info("  Press Ctrl+C to stop")
        logger.info("")

        while self._running:
            try:
                self.scan_once()
            except Exception as e:
                logger.error(f"❌ Scan cycle failed: {e}")

            if self._running:
                logger.info(f"  ⏳ Next scan in {self.interval}s...")
                # Sleep in small increments so we can respond to signals
                for _ in range(self.interval):
                    if not self._running:
                        break
                    time.sleep(1)

        # Summary
        logger.info("")
        logger.info("📊 Agent Summary")
        logger.info(f"  Scans:    {self._scan_count}")
        logger.info(f"  Tokens:   {len(self._seen_tokens)}")
        logger.info(f"  Alerts:   {self._alert_count}")
        logger.info("  Goodbye! 🛡️")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="rugcheck",
        description="🛡️  Rugcheck v2 — Solana Token Risk Scanner (Bags.fm Hackathon)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --simulate --interval 30
  %(prog)s --live --api-key YOUR_BAGS_KEY
  %(prog)s --simulate --log-file scan_log.jsonl
        """,
    )
    parser.add_argument(
        "--simulate", "-s",
        action="store_true",
        default=True,
        help="Use simulated data (default: True)",
    )
    parser.add_argument(
        "--live", "-l",
        action="store_true",
        help="Use live Bags.fm API (requires --api-key)",
    )
    parser.add_argument(
        "--api-key", "-k",
        default=None,
        help="Bags.fm API key (required for live mode)",
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=60,
        help="Seconds between scan cycles (default: 60)",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Optional JSON log file path",
    )
    parser.add_argument(
        "--webhook-url",
        default=None,
        help="Webhook URL for alerts",
    )
    parser.add_argument(
        "--telegram-bot-token",
        default=None,
        help="Telegram bot token",
    )
    parser.add_argument(
        "--telegram-chat-id",
        default=None,
        help="Telegram chat ID",
    )
    return parser


def main():
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    # Determine mode
    simulate = not args.live

    # Setup logging
    setup_logging(log_file=args.log_file)

    # Create components
    bags_client = BagsClient(
        api_key=args.api_key,
        simulate=simulate,
    )

    alert_dispatcher = AlertDispatcher(
        webhook_url=args.webhook_url,
        telegram_bot_token=args.telegram_bot_token,
        telegram_chat_id=args.telegram_chat_id,
    )

    # Create and run agent
    agent = RugcheckAgent(
        bags_client=bags_client,
        alert_dispatcher=alert_dispatcher,
        interval=args.interval,
        simulate=simulate,
    )

    agent.run()


if __name__ == "__main__":
    main()
