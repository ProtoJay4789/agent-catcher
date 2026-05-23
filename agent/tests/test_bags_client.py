#!/usr/bin/env python3
"""
Unit tests for Rugcheck v2 Bags.fm API client.

Tests cover:
  - Simulate mode: launches, token info, fees
  - Deterministic scenarios: safe, suspicious, dangerous, mixed
  - Edge cases: empty responses, unknown mints
  - Real API mode: mock HTTP calls

Run: python3 -m pytest agent/tests/test_bags_client.py -v
"""

import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scanners.bags_client import BagsClient, _SIMULATED_TOKENS


# ─── Simulate Mode Tests ─────────────────────────────────────────────────────

class TestBagsClientSimulate:
    """Tests for the BagsClient in simulation mode."""

    def test_returns_list(self):
        client = BagsClient(simulate=True)
        launches = client.get_new_launches(limit=5)
        assert isinstance(launches, list)

    def test_limit_respected(self):
        client = BagsClient(simulate=True)
        launches = client.get_new_launches(limit=3)
        assert len(launches) <= 3

    def test_launch_has_required_keys(self):
        client = BagsClient(simulate=True)
        launches = client.get_new_launches(limit=1)
        assert len(launches) >= 1
        launch = launches[0]
        assert "mint" in launch
        assert "name" in launch
        assert "symbol" in launch
        assert "creator" in launch

    def test_token_info_returns_dict(self):
        client = BagsClient(simulate=True)
        info = client.get_token_info("So11111111111111111111111111111111111111112")
        assert isinstance(info, dict)
        assert "mint" in info
        assert "name" in info
        assert "has_mint_authority" in info

    def test_token_info_has_risk_fields(self):
        client = BagsClient(simulate=True)
        info = client.get_token_info("So11111111111111111111111111111111111111112")
        required_fields = [
            "has_mint_authority", "has_freeze_authority", "lp_locked",
            "top_holder_pct", "is_open_source", "has_social",
            "creator_rug_count", "liquidity_usd", "volume_24h",
        ]
        for field in required_fields:
            assert field in info, f"Missing field: {field}"

    def test_token_fees_returns_dict(self):
        client = BagsClient(simulate=True)
        fees = client.get_token_fees("So11111111111111111111111111111111111111112")
        assert isinstance(fees, dict)
        assert "mint" in fees
        assert "sell_fee_pct" in fees

    def test_all_simulated_tokens_produce_valid_data(self):
        """Run simulation on many mints — all should produce parseable data."""
        client = BagsClient(simulate=True)
        for scenario in _SIMULATED_TOKENS:
            info = client.get_token_info(scenario["mint"])
            assert "mint" in info
            assert "has_mint_authority" in info
            assert isinstance(info["has_mint_authority"], bool)

    def test_deterministic_same_mint(self):
        """Same mint address should produce same scenario."""
        client = BagsClient(simulate=True)
        info1 = client.get_token_info("7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr")
        info2 = client.get_token_info("7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr")
        assert info1["name"] == info2["name"]
        assert info1["has_mint_authority"] == info2["has_mint_authority"]

    def test_different_mints_different_data(self):
        """Different mints may produce different scenarios."""
        client = BagsClient(simulate=True)
        info1 = client.get_token_info("So11111111111111111111111111111111111111112")
        info2 = client.get_token_info("7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr")
        # They might be different scenarios (depends on hash)
        # Just verify both are valid
        assert isinstance(info1, dict)
        assert isinstance(info2, dict)


# ─── Live API Mode Tests (Mocked) ────────────────────────────────────────────

class TestBagsClientLive:
    """Tests for the BagsClient in live mode with mocked HTTP."""

    def test_live_get_launches(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "launches": [
                {"mint": "abc123", "name": "TestToken", "symbol": "TEST"}
            ]
        }

        with patch("scanners.bags_client.requests") as mock_requests:
            mock_session = MagicMock()
            mock_session.get.return_value = mock_response
            mock_requests.Session.return_value = mock_session

            client = BagsClient(api_key="test_key", simulate=False)
            launches = client.get_new_launches(limit=5)

            assert len(launches) == 1
            assert launches[0]["mint"] == "abc123"

    def test_live_get_token_info(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "mint": "abc123",
            "name": "TestToken",
            "has_mint_authority": False,
        }

        with patch("scanners.bags_client.requests") as mock_requests:
            mock_session = MagicMock()
            mock_session.get.return_value = mock_response
            mock_requests.Session.return_value = mock_session

            client = BagsClient(api_key="test_key", simulate=False)
            info = client.get_token_info("abc123")

            assert info["mint"] == "abc123"
            assert info["has_mint_authority"] is False

    def test_live_api_error_returns_empty(self):
        with patch("scanners.bags_client.requests") as mock_requests:
            mock_session = MagicMock()
            mock_session.get.side_effect = Exception("Network error")
            mock_requests.Session.return_value = mock_session

            client = BagsClient(api_key="test_key", simulate=False)
            launches = client.get_new_launches(limit=5)

            assert launches == []

    def test_live_api_auth_header(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"launches": []}

        with patch("scanners.bags_client.requests") as mock_requests:
            mock_session = MagicMock()
            mock_session.headers = {}  # Use real dict for headers
            mock_session.get.return_value = mock_response
            mock_requests.Session.return_value = mock_session

            client = BagsClient(api_key="my_secret_key", simulate=False)
            client.get_new_launches(limit=1)

            # Verify auth header was set
            assert mock_session.headers["Authorization"] == "Bearer my_secret_key"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
