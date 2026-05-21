#!/usr/bin/env python3
"""
Integration tests for Agent Catcher — full pipeline with alert triggers.

Tests the complete E2E flow:
  token address → scan → extract factors → score → classify → alert

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

from monitor import (
    extract_risk_factors,
    calculate_risk_score,
    simulate_goplus,
    scaffold_submit,
    RISK_WEIGHTS,
    RISK_THRESHOLDS,
)
from alerts import AlertDispatcher, format_alert_json


# ─── Deterministic Pipeline Tests ─────────────────────────────────────────────

class TestDeterministicPipeline:
    """Use known raw data instead of random simulation."""

    def test_safe_token_full_pipeline(self, raw_safe, alert_dispatcher_no_webhook):
        """Safe token → LOW → no alert fired."""
        token = "0x2::sui::SUI"

        # Step 1: Parse factors
        factors = extract_risk_factors(raw_safe)
        assert factors["is_honeypot"] is False
        assert factors["is_open_source"] is True

        # Step 2: Score
        score, penalty, level = calculate_risk_score(factors)
        assert score >= 80, f"Safe token scored {score}, expected >= 80"
        assert level == "LOW"

        # Step 3: Alert check — should NOT fire for LOW
        results = alert_dispatcher_no_webhook.send(token, score, level, factors)
        assert len(results) == 0, "Safe token should not trigger alerts"

    def test_dangerous_token_full_pipeline(self, raw_dangerous, alert_dispatcher_no_webhook):
        """Dangerous token → CRITICAL → alert fired."""
        token = "0xdeadbeef"

        # Step 1: Parse factors
        factors = extract_risk_factors(raw_dangerous)
        risky_count = sum(1 for v in factors.values() if v)
        assert risky_count >= 8, f"Expected 8+ risky flags, got {risky_count}"

        # Step 2: Score
        score, penalty, level = calculate_risk_score(factors)
        assert score <= 20, f"Dangerous token scored {score}, expected <= 20"
        assert level == "CRITICAL"

        # Step 3: Alert should fire
        results = alert_dispatcher_no_webhook.send(token, score, level, factors)
        assert len(results) == 1
        assert results[0]["success"] is True

    def test_suspicious_token_full_pipeline(self, raw_suspicious, alert_dispatcher_no_webhook):
        """Suspicious token → MEDIUM or HIGH → may or may not alert."""
        token = "0xsuspicious"

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

    def test_score_59_triggers_alert(self):
        """Score 59 = HIGH → should trigger alert."""
        # Create factors that produce score ~59
        # Need penalty ~0.41
        factors = {k: False for k in RISK_WEIGHTS}
        factors["is_open_source"] = False  # +0.10
        factors["is_honeypot"] = True       # +0.20
        factors["can_take_back_liquidity"] = True  # +0.12
        # Total: 0.42 → score = 58 → HIGH

        score, _, level = calculate_risk_score(factors)
        assert level == "HIGH"
        assert 55 <= score <= 65

        d = AlertDispatcher()
        results = d.send("0xtest", score, level, factors)
        assert len(results) == 1

    def test_score_79_no_alert(self):
        """Score 79 = MEDIUM → should NOT trigger alert."""
        factors = {k: False for k in RISK_WEIGHTS}
        factors["is_open_source"] = False  # +0.10
        factors["is_proxy"] = True          # +0.05
        # Total: 0.15 → score = 85... need more penalty
        # Let's just test with known MEDIUM level
        factors["owner_change_balance"] = True  # +0.10
        # Total: 0.25 → score = 75 → MEDIUM

        score, _, level = calculate_risk_score(factors)
        assert level == "MEDIUM"

        d = AlertDispatcher()
        results = d.send("0xtest", score, level, factors)
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
        tokens = [f"0xtoken_{i}" for i in range(10)]

        batch_results = []
        for token in tokens:
            raw = simulate_goplus(token)
            factors = extract_risk_factors(raw)
            score, penalty, level = calculate_risk_score(factors)
            alerts = alert_dispatcher_no_webhook.send(token, score, level, factors)
            batch_results.append({
                "token": token,
                "score": score,
                "level": level,
                "alerted": len(alerts) > 0,
            })

        assert len(batch_results) == 10
        for r in batch_results:
            assert 0 <= r["score"] <= 100
            assert r["level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
            # If alerted, must be HIGH or CRITICAL
            if r["alerted"]:
                assert r["level"] in ("HIGH", "CRITICAL")

    def test_batch_has_mixed_levels(self):
        """With enough tokens, we should see multiple risk levels."""
        levels_seen = set()
        # Run many times to hit different random scenarios
        for i in range(200):
            raw = simulate_goplus(f"0xtoken_{i}")
            factors = extract_risk_factors(raw)
            _, _, level = calculate_risk_score(factors)
            levels_seen.add(level)

        assert "LOW" in levels_seen, "Expected at least one LOW token"
        assert "CRITICAL" in levels_seen, "Expected at least one CRITICAL token"


# ─── Full Pipeline with JSON Output ───────────────────────────────────────────

class TestPipelineWithJSONOutput:
    """Test the full pipeline produces valid JSON (like --json mode)."""

    def test_json_output_roundtrip(self):
        """Full pipeline → JSON → parse → verify fields."""
        token = "0x2::sui::SUI"
        raw = simulate_goplus(token)
        factors = extract_risk_factors(raw)
        score, penalty, level = calculate_risk_score(factors)

        output = {
            "token_address": token,
            "score": score,
            "level": level,
            "penalty": round(penalty, 4),
            "factors": factors,
            "raw": raw,
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
        factors = {"is_honeypot": True, "is_open_source": False}
        payload = format_alert_json("0xdead", 15, "CRITICAL", factors)

        # Should serialize without error
        json_str = json.dumps(payload)
        parsed = json.loads(json_str)
        assert parsed["alert"] is True


# ─── Scaffold Integration ─────────────────────────────────────────────────────

class TestScaffoldIntegration:
    """Test that scaffold_submit works in the pipeline context."""

    def test_scaffold_after_scoring(self, raw_dangerous, capsys):
        """Dangerous token → score → scaffold should not raise."""
        factors = extract_risk_factors(raw_dangerous)
        score, _, level = calculate_risk_score(factors)

        scaffold_submit("0xdead", score, level, factors, "test_agent")

        captured = capsys.readouterr()
        assert "On-Chain Submission Scaffold" in captured.out
        assert "test_agent" in captured.out


# ─── Edge Case Integration ────────────────────────────────────────────────────

class TestEdgeCaseIntegration:
    def test_empty_data_pipeline(self):
        """Empty GoPlus response should still complete the pipeline."""
        raw = {}
        factors = extract_risk_factors(raw)
        score, penalty, level = calculate_risk_score(factors)
        assert 0 <= score <= 100
        assert level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_all_none_values(self):
        """Raw data with None values should not crash."""
        raw = {
            "is_honeypot": None,
            "is_open_source": None,
            "owner_change_balance": None,
        }
        factors = extract_risk_factors(raw)
        # None != "1", so all should be False
        assert all(v is False for v in factors.values())

    def test_score_stays_bounded(self):
        """Score should never exceed [0, 100] regardless of input."""
        for _ in range(100):
            raw = simulate_goplus("0xtest")
            factors = extract_risk_factors(raw)
            score, _, _ = calculate_risk_score(factors)
            assert 0 <= score <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
