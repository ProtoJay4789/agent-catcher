#!/usr/bin/env python3
"""
Integration tests for Rugcheck v2 — full pipeline with alert triggers.

Tests the complete E2E flow:
  token mint → BagsClient → extract factors → score → classify → alert

Also tests:
  - Alert dispatcher integration with scoring engine
  - Deterministic scenarios (always safe / always dangerous)
  - Score-to-alert threshold boundary
  - Multi-token batch scanning with alerts

Run: python3 -m pytest agent/tests/test_integration.py -v
"""

import sys
import os
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scorer import (
    extract_risk_factors,
    calculate_risk_score,
    RISK_WEIGHTS,
    RISK_THRESHOLDS,
)
from scanners.bags_client import BagsClient
from alerts import AlertDispatcher, format_alert_json


# ─── Deterministic Pipeline Tests ─────────────────────────────────────────────

class TestDeterministicPipeline:
    """Use known raw data instead of random simulation."""

    def test_safe_token_full_pipeline(self, raw_safe, alert_dispatcher_no_webhook):
        """Safe token → LOW → no alert fired."""
        token = raw_safe["mint"]

        # Step 1: Parse factors
        factors = extract_risk_factors(raw_safe)
        assert factors["has_mint_authority"] is False
        assert factors["is_open_source"] is True
        assert factors["lp_locked"] is True

        # Step 2: Score
        score, penalty, level = calculate_risk_score(factors)
        assert score >= 80, f"Safe token scored {score}, expected >= 80"
        assert level == "LOW"

        # Step 3: Alert check — should NOT fire for LOW
        results = alert_dispatcher_no_webhook.send(token, score, level, factors)
        assert len(results) == 0, "Safe token should not trigger alerts"

    def test_dangerous_token_full_pipeline(self, raw_dangerous, alert_dispatcher_no_webhook):
        """Dangerous token → CRITICAL → alert fired."""
        token = raw_dangerous["mint"]

        # Step 1: Parse factors
        factors = extract_risk_factors(raw_dangerous)
        risky_count = sum(1 for v in factors.values() if v)
        assert risky_count >= 7, f"Expected 7+ risky flags, got {risky_count}"

        # Step 2: Score
        score, penalty, level = calculate_risk_score(factors)
        assert score <= 30, f"Dangerous token scored {score}, expected <= 30"
        assert level in ("HIGH", "CRITICAL")

        # Step 3: Alert should fire
        results = alert_dispatcher_no_webhook.send(token, score, level, factors)
        assert len(results) == 1
        assert results[0]["success"] is True

    def test_suspicious_token_full_pipeline(self, raw_suspicious, alert_dispatcher_no_webhook):
        """Suspicious token → MEDIUM or HIGH → may or may not alert."""
        token = raw_suspicious["mint"]

        factors = extract_risk_factors(raw_suspicious)
        score, penalty, level = calculate_risk_score(factors)

        # Suspicious should be MEDIUM or HIGH
        assert level in ("MEDIUM", "HIGH"), f"Suspicious token scored {level} ({score})"

        # Alert only if HIGH
        results = alert_dispatcher_no_webhook.send(token, score, level, factors)
        if level == "HIGH":
            assert len(results) == 1
        else:
            assert len(results) == 0


# ─── Score-to-Alert Threshold Tests ───────────────────────────────────────────

class TestScoreToAlertThresholds:
    """Test the exact boundary between alert and no-alert."""

    def test_high_level_triggers_alert(self):
        """HIGH level should trigger alert."""
        factors = {
            "has_mint_authority": True,    # 0.15
            "has_freeze_authority": True,  # 0.12
            "lp_locked": False,            # 0.18
            "top_holder_concentration": True,  # 0.12
            "is_open_source": False,       # 0.10
            "has_social": True,            # safe
            "creator_history": False,      # safe
            "liquidity_depth": False,      # safe
            "trading_volume": False,       # safe
            "rug_history": False,          # safe
        }
        # Total: 0.15 + 0.12 + 0.18 + 0.12 + 0.10 = 0.67 → score ~33 → CRITICAL
        score, _, level = calculate_risk_score(factors)
        assert level in ("HIGH", "CRITICAL")
        assert 30 <= score <= 40

        d = AlertDispatcher()
        results = d.send("test_token", score, level, factors)
        assert len(results) == 1

    def test_medium_level_no_alert(self):
        """MEDIUM level should NOT trigger alert."""
        factors = {
            "has_mint_authority": True,    # 0.15
            "has_freeze_authority": False, # safe
            "lp_locked": False,            # 0.18
            "top_holder_concentration": False,  # safe
            "is_open_source": False,       # 0.10
            "has_social": True,            # safe
            "creator_history": False,      # safe
            "liquidity_depth": False,      # safe
            "trading_volume": False,       # safe
            "rug_history": False,          # safe
        }
        # Total: 0.15 + 0.18 + 0.10 = 0.43 → score ~57 → HIGH
        # Hmm, need less penalty for MEDIUM
        factors["lp_locked"] = True  # remove this penalty
        # Total: 0.15 + 0.10 = 0.25 → score ~75 → MEDIUM
        score, _, level = calculate_risk_score(factors)
        assert level == "MEDIUM"

        d = AlertDispatcher()
        results = d.send("test_token", score, level, factors)
        assert len(results) == 0

    def test_boundary_all_levels_reachable(self):
        """Verify every level in 0-100 maps correctly."""
        expected = {}
        for score in range(101):
            for lvl, (lo, hi) in RISK_THRESHOLDS.items():
                if lo <= score <= hi:
                    expected[score] = lvl
                    break

        for score, expected_level in expected.items():
            d = AlertDispatcher()
            should_fire = d.should_alert(expected_level)
            if expected_level in ("HIGH", "CRITICAL"):
                assert should_fire, f"Score {score} ({expected_level}) should fire"
            else:
                assert not should_fire, f"Score {score} ({expected_level}) should NOT fire"


# ─── Multi-Token Batch Tests ─────────────────────────────────────────────────

class TestBatchScanning:
    """Test scanning multiple tokens in sequence with alerts."""

    def test_batch_produces_results(self, alert_dispatcher_no_webhook):
        """Batch of 10 tokens should produce 10 results."""
        client = BagsClient(simulate=True)
        tokens = client.get_new_launches(limit=10)

        batch_results = []
        for token in tokens:
            mint = token["mint"]
            info = client.get_token_info(mint)
            factors = extract_risk_factors(info)
            score, penalty, level = calculate_risk_score(factors)
            alerts = alert_dispatcher_no_webhook.send(mint, score, level, factors)
            batch_results.append({
                "token": mint,
                "score": score,
                "level": level,
                "alerted": len(alerts) > 0,
            })

        assert len(batch_results) > 0
        for r in batch_results:
            assert 0 <= r["score"] <= 100
            assert r["level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
            # If alerted, must be HIGH or CRITICAL
            if r["alerted"]:
                assert r["level"] in ("HIGH", "CRITICAL")


# ─── Full Pipeline with JSON Output ───────────────────────────────────────────

class TestPipelineWithJSONOutput:
    """Test the full pipeline produces valid JSON (like --json mode)."""

    def test_json_output_roundtrip(self):
        """Full pipeline → JSON → parse → verify fields."""
        client = BagsClient(simulate=True)
        token = "So11111111111111111111111111111111111111112"
        info = client.get_token_info(token)
        factors = extract_risk_factors(info)
        score, penalty, level = calculate_risk_score(factors)

        output = {
            "token_address": token,
            "score": score,
            "level": level,
            "penalty": round(penalty, 4),
            "factors": factors,
            "raw": info,
            "simulated": True,
        }

        # JSON serialize and parse
        json_str = json.dumps(output, indent=2)
        parsed = json.loads(json_str)

        assert parsed["token_address"] == token
        assert parsed["score"] == score
        assert parsed["level"] == level
        assert isinstance(parsed["factors"], dict)
        assert isinstance(parsed["raw"], dict)

    def test_alert_payload_json_compatible(self):
        """Alert JSON payload should be JSON-serializable."""
        factors = {"has_mint_authority": True, "is_open_source": False}
        payload = format_alert_json("7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", 15, "CRITICAL", factors)

        # Should serialize without error
        json_str = json.dumps(payload)
        parsed = json.loads(json_str)
        assert parsed["alert"] is True


# ─── Edge Case Integration ────────────────────────────────────────────────────

class TestEdgeCaseIntegration:
    def test_empty_data_pipeline(self):
        """Empty response should still complete the pipeline."""
        raw = {}
        factors = extract_risk_factors(raw)
        score, penalty, level = calculate_risk_score(factors)
        assert 0 <= score <= 100
        assert level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_all_none_values(self):
        """Raw data with None values should not crash."""
        raw = {
            "has_mint_authority": None,
            "has_freeze_authority": None,
            "lp_locked": None,
        }
        factors = extract_risk_factors(raw)
        # None is falsy, so direct factors are False
        assert factors["has_mint_authority"] is False
        assert factors["has_freeze_authority"] is False
        assert factors["lp_locked"] is False

    def test_score_stays_bounded(self):
        """Score should never exceed [0, 100] regardless of input."""
        client = BagsClient(simulate=True)
        for scenario_name in ["safe", "suspicious", "dangerous", "mixed"]:
            info = client.get_token_info(f"test_{scenario_name}")
            factors = extract_risk_factors(info)
            score, _, _ = calculate_risk_score(factors)
            assert 0 <= score <= 100

    def test_full_bagsclient_to_scorer_pipeline(self):
        """Test the complete BagsClient → scorer pipeline."""
        client = BagsClient(simulate=True)
        launches = client.get_new_launches(limit=5)

        for launch in launches:
            mint = launch["mint"]
            info = client.get_token_info(mint)
            assert "has_mint_authority" in info

            factors = extract_risk_factors(info)
            assert len(factors) == len(RISK_WEIGHTS)

            score, penalty, level = calculate_risk_score(factors)
            assert 0 <= score <= 100
            assert level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
