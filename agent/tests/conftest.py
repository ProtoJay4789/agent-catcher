#!/usr/bin/env python3
"""
Shared pytest fixtures for Rugcheck v2 tests.

Provides:
  - Mock Solana token data for all risk scenarios
  - Pre-built factor sets for the new Solana-specific risk model
  - Alert dispatcher fixtures
  - Mock Bags.fm client fixtures
"""

import pytest
import sys
import os

# Ensure agent/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scorer import RISK_WEIGHTS, RISK_THRESHOLDS


# ─── Token Mint Address Fixtures ─────────────────────────────────────────────

@pytest.fixture
def safe_token_mint():
    return "So11111111111111111111111111111111111111112"

@pytest.fixture
def dangerous_token_mint():
    return "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"

@pytest.fixture
def random_token_mint():
    return "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


# ─── Raw Token Info Fixtures (Solana-native) ─────────────────────────────────

@pytest.fixture
def raw_safe():
    """All-clear Solana token data — no risk flags."""
    return {
        "mint": "So11111111111111111111111111111111111111112",
        "name": "SafeToken",
        "symbol": "SAFE",
        "supply": 1_000_000_000,
        "decimals": 9,
        "holders": 12_500,
        "creator": "11111111111111111111111111111111",
        "creation_time": 1700000000,
        "has_mint_authority": False,
        "has_freeze_authority": False,
        "lp_locked": True,
        "top_holder_pct": 0.05,
        "is_open_source": True,
        "has_social": True,
        "creator_rug_count": 0,
        "liquidity_usd": 500_000,
        "volume_24h": 1_200_000,
    }

@pytest.fixture
def raw_dangerous():
    """Every risk flag set — classic rug/honeypot setup."""
    return {
        "mint": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
        "name": "ScamCoin",
        "symbol": "SCAM",
        "supply": 666_000_000,
        "decimals": 9,
        "holders": 15,
        "creator": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
        "creation_time": 1700000000,
        "has_mint_authority": True,
        "has_freeze_authority": True,
        "lp_locked": False,
        "top_holder_pct": 0.85,
        "is_open_source": False,
        "has_social": False,
        "creator_rug_count": 3,
        "liquidity_usd": 200,
        "volume_24h": 50,
    }

@pytest.fixture
def raw_suspicious():
    """Some risk flags — mint authority, no LP lock, new creator."""
    return {
        "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "name": "SuspiciousToken",
        "symbol": "SUSP",
        "supply": 500_000_000,
        "decimals": 9,
        "holders": 320,
        "creator": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
        "creation_time": 1700000000,
        "has_mint_authority": True,
        "has_freeze_authority": False,
        "lp_locked": False,
        "top_holder_pct": 0.35,
        "is_open_source": False,
        "has_social": True,
        "creator_rug_count": 1,
        "liquidity_usd": 15_000,
        "volume_24h": 8_000,
    }

@pytest.fixture
def raw_empty():
    """Empty response — should default to all-False factors."""
    return {}


# ─── Pre-built Factor Sets ────────────────────────────────────────────────────

@pytest.fixture
def factors_all_safe():
    """All factors safe — perfect score."""
    return {
        "has_mint_authority": False,
        "has_freeze_authority": False,
        "lp_locked": True,
        "top_holder_concentration": False,
        "is_open_source": True,
        "has_social": True,
        "creator_history": False,
        "liquidity_depth": False,
        "trading_volume": False,
        "rug_history": False,
    }

@pytest.fixture
def factors_all_risky():
    """All factors risky — worst score."""
    return {
        "has_mint_authority": True,
        "has_freeze_authority": True,
        "lp_locked": False,
        "top_holder_concentration": True,
        "is_open_source": False,
        "has_social": False,
        "creator_history": True,
        "liquidity_depth": True,
        "trading_volume": True,
        "rug_history": True,
    }

@pytest.fixture
def factors_honeypot_only():
    """Just mint authority (honeypot-like) — moderate penalty."""
    return {
        "has_mint_authority": True,
        "has_freeze_authority": False,
        "lp_locked": True,
        "top_holder_concentration": False,
        "is_open_source": True,
        "has_social": True,
        "creator_history": False,
        "liquidity_depth": False,
        "trading_volume": False,
        "rug_history": False,
    }

@pytest.fixture
def factors_critical_combo():
    """Mint authority + freeze authority + no LP lock + high concentration + no social."""
    return {
        "has_mint_authority": True,
        "has_freeze_authority": True,
        "lp_locked": False,
        "top_holder_concentration": True,
        "is_open_source": False,
        "has_social": False,
        "creator_history": False,
        "liquidity_depth": False,
        "trading_volume": False,
        "rug_history": False,
    }


# ─── Alert Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def alert_dispatcher_no_webhook():
    """Alert dispatcher with terminal only (no webhook/Telegram)."""
    from alerts import AlertDispatcher
    return AlertDispatcher()

@pytest.fixture
def alert_dispatcher_with_webhook():
    """Alert dispatcher with a mock webhook URL."""
    from alerts import AlertDispatcher
    return AlertDispatcher(webhook_url="https://httpbin.org/post")

@pytest.fixture
def sample_alert_payload():
    """Sample structured alert payload."""
    return {
        "token_address": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
        "score": 25,
        "level": "CRITICAL",
        "factors": {
            "has_mint_authority": True,
            "has_freeze_authority": True,
            "lp_locked": False,
            "top_holder_concentration": True,
            "is_open_source": False,
            "has_social": False,
            "creator_history": True,
            "liquidity_depth": True,
            "trading_volume": False,
            "rug_history": True,
        },
        "agent_id": "rugcheck_v2",
    }
