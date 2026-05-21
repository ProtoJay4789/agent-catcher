#!/usr/bin/env python3
"""
Shared pytest fixtures for Agent Catcher tests.

Provides:
  - Mock token data for all risk scenarios
  - Pre-built factor sets
  - Alert dispatcher fixtures
  - Mock GoPlus responses
"""

import pytest
import sys
import os

# Ensure agent/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from monitor import RISK_WEIGHTS, RISK_THRESHOLDS


# ─── Token Address Fixtures ───────────────────────────────────────────────────

@pytest.fixture
def safe_token_address():
    return "0x2::sui::SUI"

@pytest.fixture
def dangerous_token_address():
    return "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"

@pytest.fixture
def random_token_address():
    return "0xtoken_abc123_test"


# ─── Raw GoPlus Data Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def raw_safe():
    """All-clear GoPlus data — no risk flags."""
    return {
        "is_honeypot": "0",
        "is_open_source": "1",
        "owner_change_balance": "0",
        "can_take_back_liquidity": "0",
        "hidden_owner": "0",
        "selfdestruct": "0",
        "external_call": "0",
        "is_proxy": "0",
        "malicious_behavior": "0",
        "slippage_modifiable": "0",
        "is_blacklisted": "0",
        "token_name": "SafeToken",
        "token_symbol": "SAFE",
        "holder_count": "12500",
        "total_supply": "1000000000",
        "owner_address": "0x0000000000000000000000000000000000000000",
    }

@pytest.fixture
def raw_dangerous():
    """Every risk flag is set — honeypot, hidden owner, self-destruct, etc."""
    return {
        "is_honeypot": "1",
        "is_open_source": "0",
        "owner_change_balance": "1",
        "can_take_back_liquidity": "1",
        "hidden_owner": "1",
        "selfdestruct": "1",
        "external_call": "1",
        "is_proxy": "1",
        "malicious_behavior": "1",
        "slippage_modifiable": "1",
        "is_blacklisted": "1",
        "token_name": "ScamCoin",
        "token_symbol": "SCAM",
        "holder_count": "15",
        "total_supply": "666000000",
        "owner_address": "0x1234567890abcdef1234567890abcdef12345678",
    }

@pytest.fixture
def raw_suspicious():
    """Some risk flags — hidden owner, proxy, slippage modifiable."""
    return {
        "is_honeypot": "0",
        "is_open_source": "0",
        "owner_change_balance": "1",
        "can_take_back_liquidity": "0",
        "hidden_owner": "1",
        "selfdestruct": "0",
        "external_call": "1",
        "is_proxy": "1",
        "malicious_behavior": "0",
        "slippage_modifiable": "1",
        "is_blacklisted": "0",
        "token_name": "SuspiciousToken",
        "token_symbol": "SUSP",
        "holder_count": "320",
        "total_supply": "500000000",
        "owner_address": "0xdeadbeefdeadbeefdeadbeefdeadbeef",
    }

@pytest.fixture
def raw_empty():
    """Empty GoPlus response — should default to safe-ish."""
    return {}


# ─── Pre-built Factor Sets ────────────────────────────────────────────────────

@pytest.fixture
def factors_all_safe():
    """All factors False, open source True — perfect score."""
    f = {k: False for k in RISK_WEIGHTS}
    f["is_open_source"] = True
    return f

@pytest.fixture
def factors_all_risky():
    """All factors True (except open_source=False) — worst score."""
    f = {k: True for k in RISK_WEIGHTS}
    f["is_open_source"] = False
    return f

@pytest.fixture
def factors_honeypot_only():
    """Just honeypot flag — moderate penalty."""
    f = {k: False for k in RISK_WEIGHTS}
    f["is_open_source"] = True
    f["is_honeypot"] = True
    return f

@pytest.fixture
def factors_critical_combo():
    """Honeypot + can_take_liquidity + hidden_owner + selfdestruct + malicious."""
    f = {k: False for k in RISK_WEIGHTS}
    f["is_open_source"] = False
    f["is_honeypot"] = True
    f["can_take_back_liquidity"] = True
    f["hidden_owner"] = True
    f["selfdestruct"] = True
    f["malicious_behavior"] = True
    return f


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
        "token_address": "0xdeadbeef",
        "score": 25,
        "level": "CRITICAL",
        "factors": {
            "is_honeypot": True,
            "is_open_source": False,
            "owner_change_balance": True,
            "can_take_back_liquidity": True,
            "hidden_owner": True,
            "selfdestruct": False,
            "external_call": False,
            "is_proxy": False,
            "malicious_behavior": True,
            "slippage_modifiable": False,
            "is_blacklisted": False,
        },
        "agent_id": "gentech_agent_v1",
    }
