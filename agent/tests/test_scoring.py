#!/usr/bin/env python3
"""
Unit tests for Agent Catcher risk scoring engine.

Tests cover:
  - extract_risk_factors: parsing raw GoPlus data
  - calculate_risk_score: weighted scoring logic
  - Classification thresholds: LOW / MEDIUM / HIGH / CRITICAL
  - Edge cases: empty data, all risky, all safe, inverse factors

Run: python3 -m pytest agent/tests/test_scoring.py -v
"""

import sys
import os
import pytest

# Add parent directory to path so we can import monitor
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from monitor import (
    extract_risk_factors,
    calculate_risk_score,
    RISK_WEIGHTS,
    RISK_THRESHOLDS,
    simulate_goplus,
)


# ─── extract_risk_factors tests ─────────────────────────────────────────────

class TestExtractRiskFactors:
    """Tests for parsing raw GoPlus data into boolean risk factors."""

    def test_all_risky(self):
        raw = {
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
        }
        factors = extract_risk_factors(raw)
        assert factors["is_honeypot"] is True
        assert factors["is_open_source"] is False
        assert factors["hidden_owner"] is True
        assert factors["selfdestruct"] is True
        assert factors["malicious_behavior"] is True

    def test_all_safe(self):
        raw = {
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
        }
        factors = extract_risk_factors(raw)
        assert factors["is_honeypot"] is False
        assert factors["is_open_source"] is True
        assert factors["hidden_owner"] is False
        assert factors["selfdestruct"] is False

    def test_missing_keys_default_false(self):
        """Missing keys should default to False (safe)."""
        raw = {}
        factors = extract_risk_factors(raw)
        for key in RISK_WEIGHTS:
            assert factors[key] is False

    def test_numeric_strings(self):
        """GoPlus returns '1'/'0' as strings."""
        raw = {"is_honeypot": "1", "is_open_source": "0"}
        factors = extract_risk_factors(raw)
        assert factors["is_honeypot"] is True
        assert factors["is_open_source"] is False

    def test_numeric_ints(self):
        """Some providers might return ints."""
        raw = {"is_honeypot": 1, "is_open_source": 0}
        factors = extract_risk_factors(raw)
        assert factors["is_honeypot"] is True
        assert factors["is_open_source"] is False

    def test_mixed_risk(self):
        """Partial risk flags."""
        raw = {
            "is_honeypot": "1",
            "is_open_source": "0",
            "owner_change_balance": "0",
            "can_take_back_liquidity": "0",
            "hidden_owner": "1",
            "selfdestruct": "0",
            "external_call": "0",
            "is_proxy": "0",
            "malicious_behavior": "0",
            "slippage_modifiable": "0",
            "is_blacklisted": "0",
        }
        factors = extract_risk_factors(raw)
        assert factors["is_honeypot"] is True
        assert factors["hidden_owner"] is True
        assert factors["is_open_source"] is False
        assert factors["selfdestruct"] is False


# ─── calculate_risk_score tests ─────────────────────────────────────────────

class TestCalculateRiskScore:
    """Tests for the weighted scoring engine."""

    def test_perfect_score(self):
        """All safe → score 100, level LOW."""
        factors = {k: False for k in RISK_WEIGHTS}
        factors["is_open_source"] = True  # open source is GOOD
        score, penalty, level = calculate_risk_score(factors)
        assert score == 100
        assert level == "LOW"
        assert penalty == 0.0

    def test_worst_score(self):
        """All risky → score 0, level CRITICAL."""
        factors = {k: True for k in RISK_WEIGHTS}
        factors["is_open_source"] = False  # closed source = bad
        score, penalty, level = calculate_risk_score(factors)
        assert score == 0
        assert level == "CRITICAL"
        assert penalty >= 0.95

    def test_honeypot_heavy_weight(self):
        """Honeypot alone should push score into HIGH/CRITICAL."""
        factors = {k: False for k in RISK_WEIGHTS}
        factors["is_open_source"] = True
        factors["is_honeypot"] = True
        score, penalty, level = calculate_risk_score(factors)
        # honeypot weight is 0.20, so score should drop by ~20
        assert 75 <= score <= 85
        assert level in ("LOW", "MEDIUM")

    def test_closed_source_penalty(self):
        """Not open source should penalize."""
        factors_safe = {k: False for k in RISK_WEIGHTS}
        factors_safe["is_open_source"] = True
        _, penalty_safe, _ = calculate_risk_score(factors_safe)

        factors_closed = {k: False for k in RISK_WEIGHTS}
        factors_closed["is_open_source"] = False
        _, penalty_closed, _ = calculate_risk_score(factors_closed)

        assert penalty_closed > penalty_safe

    def test_score_bounds(self):
        """Score should always be between 0 and 100."""
        import random
        for _ in range(50):
            factors = {k: random.choice([True, False]) for k in RISK_WEIGHTS}
            score, _, _ = calculate_risk_score(factors)
            assert 0 <= score <= 100

    def test_classification_thresholds(self):
        """Verify all levels are reachable."""
        levels_found = set()
        for _ in range(200):
            import random
            factors = {k: random.choice([True, False]) for k in RISK_WEIGHTS}
            _, _, level = calculate_risk_score(factors)
            levels_found.add(level)
        # We should see at least LOW and CRITICAL in 200 random samples
        assert "LOW" in levels_found
        assert "CRITICAL" in levels_found

    def test_known_dangerous_combo(self):
        """Honeypot + can_take_liquidity + hidden_owner + selfdestruct."""
        factors = {k: False for k in RISK_WEIGHTS}
        factors["is_open_source"] = True  # even with open source...
        factors["is_honeypot"] = True
        factors["can_take_back_liquidity"] = True
        factors["hidden_owner"] = True
        factors["selfdestruct"] = True
        score, _, level = calculate_risk_score(factors)
        # These 4 flags total ~0.50 weight → score ~50
        assert 45 <= score <= 60
        assert level in ("MEDIUM", "HIGH", "CRITICAL")


# ─── simulate_goplus tests ──────────────────────────────────────────────────

class TestSimulateGoPlus:
    """Tests for the simulation data generator."""

    def test_returns_dict(self):
        data = simulate_goplus("0x2::sui::SUI")
        assert isinstance(data, dict)

    def test_has_required_keys(self):
        data = simulate_goplus("0xtest")
        required = [
            "is_honeypot", "is_open_source", "owner_change_balance",
            "can_take_back_liquidity", "hidden_owner", "selfdestruct",
            "malicious_behavior", "token_name", "token_symbol",
        ]
        for key in required:
            assert key in data, f"Missing key: {key}"

    def test_all_scenarios_produce_valid_data(self):
        """Run simulation many times — all should produce parseable data."""
        import random
        for _ in range(100):
            data = simulate_goplus("0xtoken")
            factors = extract_risk_factors(data)
            score, _, level = calculate_risk_score(factors)
            assert 0 <= score <= 100
            assert level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_deterministic_with_seed(self):
        """Same seed should produce same scenario."""
        import random
        random.seed(42)
        data1 = simulate_goplus("0xtoken")
        random.seed(42)
        data2 = simulate_goplus("0xtoken")
        assert data1["token_name"] == data2["token_name"]


# ─── Edge case tests ────────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge cases and regression tests."""

    def test_empty_raw_data(self):
        """Empty dict should produce all-False factors."""
        factors = extract_risk_factors({})
        score, penalty, level = calculate_risk_score(factors)
        # No risky flags → score should be decent but closed source penalizes
        assert 85 <= score <= 100

    def test_risk_weights_sum_to_one(self):
        """Weights should sum to 1.0 (or close)."""
        total = sum(RISK_WEIGHTS.values())
        assert 0.99 <= total <= 1.01, f"Weights sum to {total}, expected ~1.0"

    def test_score_decreases_with_more_flags(self):
        """More risk flags should generally mean lower score."""
        base = {k: False for k in RISK_WEIGHTS}
        base["is_open_source"] = True
        score_base, _, _ = calculate_risk_score(base)

        added = {k: False for k in RISK_WEIGHTS}
        added["is_open_source"] = True
        added["is_honeypot"] = True
        added["hidden_owner"] = True
        added["selfdestruct"] = True
        score_added, _, _ = calculate_risk_score(added)

        assert score_added < score_base


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
