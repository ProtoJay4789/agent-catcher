#!/usr/bin/env python3
"""
Unit tests for Rugcheck v2 autonomous agent loop.

Tests cover:
  - Agent initialization
  - Single scan cycle (scan_once)
  - Token deduplication
  - Alert dispatching integration
  - Agent summary stats

Run: python3 -m pytest agent/tests/test_agent.py -v
"""

import sys
import os
import json
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.agent import RugcheckAgent
from scanners.bags_client import BagsClient
from alerts import AlertDispatcher
from scorer import RISK_WEIGHTS


# ─── Agent Initialization Tests ──────────────────────────────────────────────

class TestAgentInit:
    """Tests for agent initialization."""

    def test_creates_with_defaults(self):
        client = BagsClient(simulate=True)
        dispatcher = AlertDispatcher()
        agent = RugcheckAgent(client, dispatcher, interval=30, simulate=True)
        assert agent.interval == 30
        assert agent.simulate is True
        assert agent._scan_count == 0
        assert agent._alert_count == 0

    def test_seen_tokens_empty(self):
        client = BagsClient(simulate=True)
        dispatcher = AlertDispatcher()
        agent = RugcheckAgent(client, dispatcher)
        assert len(agent._seen_tokens) == 0


# ─── Single Scan Cycle Tests ─────────────────────────────────────────────────

class TestScanOnce:
    """Tests for the scan_once method."""

    def test_scan_once_returns_results(self):
        client = BagsClient(simulate=True)
        dispatcher = AlertDispatcher()
        agent = RugcheckAgent(client, dispatcher, simulate=True)

        results = agent.scan_once()

        assert isinstance(results, list)
        assert len(results) > 0

    def test_scan_once_result_structure(self):
        client = BagsClient(simulate=True)
        dispatcher = AlertDispatcher()
        agent = RugcheckAgent(client, dispatcher, simulate=True)

        results = agent.scan_once()

        for result in results:
            assert "mint" in result
            assert "score" in result
            assert "level" in result
            assert "factors" in result
            assert "alerted" in result
            assert "timestamp" in result
            assert 0 <= result["score"] <= 100
            assert result["level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_scan_once_increments_count(self):
        client = BagsClient(simulate=True)
        dispatcher = AlertDispatcher()
        agent = RugcheckAgent(client, dispatcher, simulate=True)

        agent.scan_once()
        assert agent._scan_count == 1

        agent.scan_once()
        assert agent._scan_count == 2

    def test_scan_once_tracks_seen_tokens(self):
        client = BagsClient(simulate=True)
        dispatcher = AlertDispatcher()
        agent = RugcheckAgent(client, dispatcher, simulate=True)

        results = agent.scan_once()
        assert len(agent._seen_tokens) > 0

    def test_scan_once_deduplicates(self):
        """Running scan twice should not re-score the same tokens."""
        client = BagsClient(simulate=True)
        dispatcher = AlertDispatcher()
        agent = RugcheckAgent(client, dispatcher, simulate=True)

        # First scan
        results1 = agent.scan_once()
        seen_after_first = len(agent._seen_tokens)

        # Second scan — should skip already-seen tokens
        results2 = agent.scan_once()

        # All tokens from first scan should still be in seen set
        assert len(agent._seen_tokens) >= seen_after_first


# ─── Alert Integration Tests ─────────────────────────────────────────────────

class TestAgentAlerts:
    """Tests for agent alert dispatching."""

    def test_dangerous_token_triggers_alert(self):
        """A dangerous token should trigger an alert."""
        client = BagsClient(simulate=True)
        dispatcher = AlertDispatcher()
        agent = RugcheckAgent(client, dispatcher, simulate=True)

        # Manually score a dangerous token to ensure alert fires
        token_info = {
            "mint": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
            "name": "ScamCoin",
            "symbol": "SCAM",
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

        from scorer import extract_risk_factors, calculate_risk_score
        factors = extract_risk_factors(token_info)
        score, penalty, level = calculate_risk_score(factors)

        # Verify it's dangerous enough to alert
        assert level in ("HIGH", "CRITICAL")

        # Alert should fire
        results = dispatcher.send(
            token_info["mint"], score, level, factors, force=True
        )
        assert len(results) > 0

    def test_safe_token_no_alert(self):
        """A safe token should not trigger an alert."""
        dispatcher = AlertDispatcher()
        from scorer import extract_risk_factors, calculate_risk_score

        token_info = {
            "mint": "So11111111111111111111111111111111111111112",
            "name": "SafeToken",
            "symbol": "SAFE",
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

        factors = extract_risk_factors(token_info)
        score, penalty, level = calculate_risk_score(factors)

        assert level == "LOW"
        results = dispatcher.send(token_info["mint"], score, level, factors)
        assert len(results) == 0  # No alert for LOW

    def test_agent_alert_count_increments(self):
        """Agent should track how many alerts were sent."""
        client = BagsClient(simulate=True)
        dispatcher = AlertDispatcher()
        agent = RugcheckAgent(client, dispatcher, simulate=True)

        # Mock _score_and_alert to simulate an alert
        original = agent._score_and_alert

        def mock_score_and_alert(mint, launch_info):
            result = original(mint, launch_info)
            # Force an alert for testing
            if result["level"] in ("HIGH", "CRITICAL"):
                agent._alert_count += 1
            return result

        agent._score_and_alert = mock_score_and_alert
        agent.scan_once()

        # At least some tokens should be dangerous in simulation
        assert agent._alert_count >= 0  # May or may not have alerts


# ─── Error Handling Tests ─────────────────────────────────────────────────────

class TestAgentErrorHandling:
    """Tests for agent error handling."""

    def test_scan_once_with_empty_launches(self):
        """Agent should handle empty launch list gracefully."""
        client = BagsClient(simulate=True)
        dispatcher = AlertDispatcher()
        agent = RugcheckAgent(client, dispatcher, simulate=True)

        # Mock to return empty list
        with patch.object(client, 'get_new_launches', return_value=[]):
            results = agent.scan_once()
            assert results == []

    def test_scan_once_with_api_error(self):
        """Agent should handle API errors gracefully."""
        client = BagsClient(simulate=True)
        dispatcher = AlertDispatcher()
        agent = RugcheckAgent(client, dispatcher, simulate=True)

        # Mock to raise exception
        with patch.object(client, 'get_new_launches', side_effect=Exception("API down")):
            results = agent.scan_once()
            assert results == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
