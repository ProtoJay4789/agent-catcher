#!/usr/bin/env python3
"""
Rugcheck v2 — Bags.fm API Client
=================================
HTTP client for the Bags.fm token launch platform API.

Supports both live API calls and simulate mode that generates realistic
mock data for safe, suspicious, and dangerous token scenarios.

Usage:
    from scanners.bags_client import BagsClient
    client = BagsClient(api_key="...", simulate=True)
    launches = client.get_new_launches(limit=10)
    token_info = client.get_token_info(mint_address)
"""

import random
import time
from typing import Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None


# ─── Constants ────────────────────────────────────────────────────────────────

BASE_URL = "https://api.bags.fm/v2"


# ─── Simulated Token Scenarios ───────────────────────────────────────────────

_SIMULATED_TOKENS = [
    # Safe token — legit project with good structure
    {
        "scenario": "safe",
        "mint": "So11111111111111111111111111111111111111112",
        "name": "SolanaSafe",
        "symbol": "SSAFE",
        "supply": 1_000_000_000,
        "decimals": 9,
        "holders": 12_500,
        "creator": "11111111111111111111111111111111",
        "creation_time": int(time.time()) - 86400 * 30,
        "has_mint_authority": False,
        "has_freeze_authority": False,
        "lp_locked": True,
        "top_holder_pct": 0.05,
        "is_open_source": True,
        "has_social": True,
        "creator_rug_count": 0,
        "liquidity_usd": 500_000,
        "volume_24h": 1_200_000,
    },
    # Suspicious token — some red flags
    {
        "scenario": "suspicious",
        "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "name": "MemeRug",
        "symbol": "MRUG",
        "supply": 500_000_000,
        "decimals": 9,
        "holders": 320,
        "creator": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
        "creation_time": int(time.time()) - 86400 * 3,
        "has_mint_authority": True,
        "has_freeze_authority": False,
        "lp_locked": False,
        "top_holder_pct": 0.35,
        "is_open_source": False,
        "has_social": True,
        "creator_rug_count": 1,
        "liquidity_usd": 15_000,
        "volume_24h": 8_000,
    },
    # Dangerous token — classic rug setup
    {
        "scenario": "dangerous",
        "mint": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
        "name": "ScamCoin",
        "symbol": "SCAM",
        "supply": 666_000_000,
        "decimals": 9,
        "holders": 15,
        "creator": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
        "creation_time": int(time.time()) - 3600,
        "has_mint_authority": True,
        "has_freeze_authority": True,
        "lp_locked": False,
        "top_holder_pct": 0.85,
        "is_open_source": False,
        "has_social": False,
        "creator_rug_count": 3,
        "liquidity_usd": 200,
        "volume_24h": 50,
    },
    # Mixed — mostly safe but one or two flags
    {
        "scenario": "mixed",
        "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "name": "ChillToken",
        "symbol": "CHILL",
        "supply": 200_000_000,
        "decimals": 6,
        "holders": 4_800,
        "creator": "DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh",
        "creation_time": int(time.time()) - 86400 * 180,
        "has_mint_authority": False,
        "has_freeze_authority": False,
        "lp_locked": True,
        "top_holder_pct": 0.12,
        "is_open_source": True,
        "has_social": True,
        "creator_rug_count": 0,
        "liquidity_usd": 350_000,
        "volume_24h": 600_000,
    },
]


# ─── BagsClient ──────────────────────────────────────────────────────────────

class BagsClient:
    """
    HTTP client for the Bags.fm token launch API.

    In simulate mode, returns realistic mock data without hitting the network.
    In live mode, calls Bags.fm v2 API endpoints with API key authentication.
    """

    def __init__(self, api_key: Optional[str] = None, simulate: bool = True):
        """
        Initialize the Bags.fm client.

        Args:
            api_key: Bags.fm API key. Required for live mode.
            simulate: If True, use mock data instead of live API calls.
        """
        self.api_key = api_key
        self.simulate = simulate
        self.base_url = BASE_URL
        self._session = None

    def _get_session(self):
        """Get or create a requests session with auth headers."""
        if self._session is None:
            if requests is None:
                raise ImportError("requests library is required for live API calls")
            self._session = requests.Session()
            if self.api_key:
                self._session.headers["Authorization"] = f"Bearer {self.api_key}"
            self._session.headers["Content-Type"] = "application/json"
        return self._session

    def get_new_launches(self, limit: int = 10) -> List[Dict]:
        """
        Fetch newly launched tokens from Bags.fm.

        Args:
            limit: Maximum number of launches to return.

        Returns:
            List of token dicts with mint address and basic info.
        """
        if self.simulate:
            return self._simulate_launches(limit)

        session = self._get_session()
        url = f"{self.base_url}/launches?limit={limit}"
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return data.get("launches", data.get("data", []))
        except Exception as e:
            print(f"❌ Bags.fm API request failed: {e}")
            return []

    def get_token_info(self, mint_address: str) -> Dict:
        """
        Fetch detailed token information for a given mint address.

        Args:
            mint_address: Solana token mint address.

        Returns:
            Dict with name, symbol, supply, holders, lp_info, creator, etc.
        """
        if self.simulate:
            return self._simulate_token_info(mint_address)

        session = self._get_session()
        url = f"{self.base_url}/tokens/{mint_address}"
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"❌ Bags.fm token info request failed: {e}")
            return {}

    def get_token_fees(self, mint_address: str) -> Dict:
        """
        Fetch fee/trading data for a token.

        Args:
            mint_address: Solana token mint address.

        Returns:
            Dict with fee and volume data.
        """
        if self.simulate:
            return self._simulate_token_fees(mint_address)

        session = self._get_session()
        url = f"{self.base_url}/tokens/{mint_address}/fees"
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"❌ Bags.fm token fees request failed: {e}")
            return {}

    # ─── Simulation Methods ──────────────────────────────────────────────

    def _simulate_launches(self, limit: int) -> List[Dict]:
        """Generate simulated new token launches."""
        count = min(limit, len(_SIMULATED_TOKENS))
        selected = random.sample(_SIMULATED_TOKENS, count)
        return [
            {
                "mint": t["mint"],
                "name": t["name"],
                "symbol": t["symbol"],
                "creator": t["creator"],
                "creation_time": t["creation_time"],
            }
            for t in selected
        ]

    def _simulate_token_info(self, mint_address: str) -> Dict:
        """Generate simulated token info for a given mint address."""
        # Pick a scenario based on the hash of the mint address for determinism
        idx = hash(mint_address) % len(_SIMULATED_TOKENS)
        scenario = _SIMULATED_TOKENS[idx]

        return {
            "mint": mint_address,
            "name": scenario["name"],
            "symbol": scenario["symbol"],
            "supply": scenario["supply"],
            "decimals": scenario["decimals"],
            "holders": scenario["holders"],
            "creator": scenario["creator"],
            "creation_time": scenario["creation_time"],
            "has_mint_authority": scenario["has_mint_authority"],
            "has_freeze_authority": scenario["has_freeze_authority"],
            "lp_locked": scenario["lp_locked"],
            "top_holder_pct": scenario["top_holder_pct"],
            "is_open_source": scenario["is_open_source"],
            "has_social": scenario["has_social"],
            "creator_rug_count": scenario["creator_rug_count"],
            "liquidity_usd": scenario["liquidity_usd"],
            "volume_24h": scenario["volume_24h"],
        }

    def _simulate_token_fees(self, mint_address: str) -> Dict:
        """Generate simulated fee data."""
        idx = hash(mint_address) % len(_SIMULATED_TOKENS)
        scenario = _SIMULATED_TOKENS[idx]

        base_fee = scenario["liquidity_usd"] * 0.003
        return {
            "mint": mint_address,
            "buy_fee_pct": 0.0,
            "sell_fee_pct": round(random.uniform(0, 0.10) if scenario["scenario"] == "dangerous" else 0.0, 4),
            "total_fees_24h": round(base_fee, 2),
            "fee_trend": "stable",
        }
