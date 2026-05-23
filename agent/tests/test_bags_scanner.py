#!/usr/bin/env python3
"""
Unit tests for Rugcheck Bags Token Scanner.

Tests cover:
  - extract_solana_risk_factors: parsing Bags + Solana data
  - calculate_risk_score: weighted scoring logic
  - Classification thresholds: LOW / MEDIUM / HIGH / CRITICAL
  - Simulation mode: realistic fake data generation
  - Edge cases: empty data, all risky, all safe

Run: python3 -m pytest agent/tests/test_bags_scanner.py -v
"""

import sys
import os
import pytest

# Add parent directory to path so we can import bags_scanner
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bags_scanner import (
    extract_solana_risk_factors,
    calculate_risk_score,
    simulate_token_data,
    RISK_WEIGHTS,
    RISK_THRESHOLDS,
)


# ─── extract_solana_risk_factors tests ────────────────────────────────────────

class TestExtractSolanaRiskFactors:
    """Tests for parsing Bags + Solana data into boolean risk factors."""

    def test_all_safe(self):
        """All safe conditions → all factors False."""
        token_data = {
            "mintAuthority": None,
            "freezeAuthority": None,
            "holderCount": 12500,
            "createdAt": 1000000000,
            "creatorRevealed": True,
            "flagged": False,
            "verified": True,
            "social": {"website": "https://example.com", "twitter": "@example"},
        }
        holders = [
            {"address": "0x0001", "percentage": 5.0},
            {"address": "0x0002", "percentage": 3.0},
        ]
        lp_data = {"totalValueLocked": 250000, "isLocked": True}
        
        factors = extract_solana_risk_factors(token_data, holders, lp_data)
        
        assert factors["mint_authority_active"] is False
        assert factors["freeze_authority_active"] is False
        assert factors["low_liquidity"] is False
        assert factors["lp_not_locked"] is False
        assert factors["high_concentration"] is False
        assert factors["no_social_presence"] is False
        assert factors["recent_creation"] is False
        assert factors["hidden_owner"] is False
        assert factors["malicious_behavior"] is False
        assert factors["low_holder_count"] is False
        assert factors["no_contract_verified"] is False

    def test_all_risky(self):
        """All risky conditions → all factors True."""
        token_data = {
            "mintAuthority": "0xdead...beef",
            "freezeAuthority": "0xdead...beef",
            "holderCount": 15,
            "createdAt": 1000,  # very old, but we'll test recent separately
            "creatorRevealed": False,
            "flagged": True,
            "verified": False,
            "social": {},
        }
        holders = [
            {"address": "0xdead...beef", "percentage": 85.0},
        ]
        lp_data = {"totalValueLocked": 500, "isLocked": False}
        
        factors = extract_solana_risk_factors(token_data, holders, lp_data)
        
        assert factors["mint_authority_active"] is True
        assert factors["freeze_authority_active"] is True
        assert factors["low_liquidity"] is True
        assert factors["lp_not_locked"] is True
        assert factors["high_concentration"] is True
        assert factors["no_social_presence"] is True
        assert factors["hidden_owner"] is True
        assert factors["malicious_behavior"] is True
        assert factors["low_holder_count"] is True
        assert factors["no_contract_verified"] is True

    def test_mint_authority_check(self):
        """Mint authority present → risky."""
        token_with_mint = {"mintAuthority": "0x1234"}
        token_without_mint = {"mintAuthority": None}
        
        factors_with = extract_solana_risk_factors(token_with_mint, [], {})
        factors_without = extract_solana_risk_factors(token_without_mint, [], {})
        
        assert factors_with["mint_authority_active"] is True
        assert factors_without["mint_authority_active"] is False

    def test_freeze_authority_check(self):
        """Freeze authority present → risky."""
        token_with_freeze = {"freezeAuthority": "0x1234"}
        token_without_freeze = {"freezeAuthority": None}
        
        factors_with = extract_solana_risk_factors(token_with_freeze, [], {})
        factors_without = extract_solana_risk_factors(token_without_freeze, [], {})
        
        assert factors_with["freeze_authority_active"] is True
        assert factors_without["freeze_authority_active"] is False

    def test_low_liquidity_check(self):
        """LP < $10K → low liquidity."""
        lp_low = {"totalValueLocked": 5000}
        lp_high = {"totalValueLocked": 50000}
        
        factors_low = extract_solana_risk_factors({}, [], lp_low)
        factors_high = extract_solana_risk_factors({}, [], lp_high)
        
        assert factors_low["low_liquidity"] is True
        assert factors_high["low_liquidity"] is False

    def test_lp_lock_check(self):
        """LP not locked → risky."""
        lp_locked = {"totalValueLocked": 100000, "isLocked": True}
        lp_unlocked = {"totalValueLocked": 100000, "isLocked": False}
        
        factors_locked = extract_solana_risk_factors({}, [], lp_locked)
        factors_unlocked = extract_solana_risk_factors({}, [], lp_unlocked)
        
        assert factors_locked["lp_not_locked"] is False
        assert factors_unlocked["lp_not_locked"] is True

    def test_high_concentration_check(self):
        """Top holder > 30% → high concentration."""
        holders_concentrated = [{"address": "0x1234", "percentage": 45.0}]
        holders_distributed = [{"address": "0x1234", "percentage": 15.0}]
        
        factors_conc = extract_solana_risk_factors({}, holders_concentrated, {})
        factors_dist = extract_solana_risk_factors({}, holders_distributed, {})
        
        assert factors_conc["high_concentration"] is True
        assert factors_dist["high_concentration"] is False

    def test_social_presence_check(self):
        """No social links → risky."""
        social_full = {"website": "https://example.com", "twitter": "@example"}
        social_empty = {}
        social_partial = {"telegram": "t.me/example"}
        
        factors_full = extract_solana_risk_factors({"social": social_full}, [], {})
        factors_empty = extract_solana_risk_factors({"social": social_empty}, [], {})
        factors_partial = extract_solana_risk_factors({"social": social_partial}, [], {})
        
        assert factors_full["no_social_presence"] is False
        assert factors_empty["no_social_presence"] is True
        assert factors_partial["no_social_presence"] is False

    def test_recent_creation_check(self):
        """Created < 24h ago → risky."""
        import time
        
        recent = {"createdAt": time.time() - 3600}  # 1 hour ago
        old = {"createdAt": time.time() - 86400 * 7}  # 7 days ago
        
        factors_recent = extract_solana_risk_factors(recent, [], {})
        factors_old = extract_solana_risk_factors(old, [], {})
        
        assert factors_recent["recent_creation"] is True
        assert factors_old["recent_creation"] is False

    def test_missing_data_defaults(self):
        """Missing data: some flags correctly default to risky, others to safe."""
        factors = extract_solana_risk_factors({}, [], {})
        
        # Should be False (safe) with empty data
        assert factors["mint_authority_active"] is False
        assert factors["freeze_authority_active"] is False
        assert factors["high_concentration"] is False
        assert factors["recent_creation"] is False
        assert factors["malicious_behavior"] is False
        
        # Should be True (risky) with empty data — no data = suspicious
        assert factors["low_liquidity"] is True  # $0 TVL
        assert factors["lp_not_locked"] is True  # no lock info
        assert factors["no_social_presence"] is True  # no social
        assert factors["hidden_owner"] is True  # not revealed
        assert factors["low_holder_count"] is True  # 0 holders
        assert factors["no_contract_verified"] is True  # not verified


# ─── calculate_risk_score tests ───────────────────────────────────────────────

class TestCalculateRiskScore:
    """Tests for the weighted scoring engine."""

    def test_perfect_score(self):
        """All safe → score 100, level LOW."""
        factors = {k: False for k in RISK_WEIGHTS}
        score, penalty, level = calculate_risk_score(factors)
        assert score == 100
        assert level == "LOW"
        assert penalty == 0.0

    def test_worst_score(self):
        """All risky → score 0, level CRITICAL."""
        factors = {k: True for k in RISK_WEIGHTS}
        score, penalty, level = calculate_risk_score(factors)
        assert score == 0
        assert level == "CRITICAL"
        assert penalty >= 0.95

    def test_mint_authority_heavy_weight(self):
        """Mint authority alone should drop score significantly."""
        factors = {k: False for k in RISK_WEIGHTS}
        factors["mint_authority_active"] = True
        score, penalty, level = calculate_risk_score(factors)
        # mint_authority weight is 0.18, so score should drop by ~18
        assert 80 <= score <= 85

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
        assert "LOW" in levels_found
        assert "CRITICAL" in levels_found

    def test_known_dangerous_combo(self):
        """Mint + freeze + low liquidity + no LP lock."""
        factors = {k: False for k in RISK_WEIGHTS}
        factors["mint_authority_active"] = True
        factors["freeze_authority_active"] = True
        factors["low_liquidity"] = True
        factors["lp_not_locked"] = True
        score, _, level = calculate_risk_score(factors)
        # These 4 flags total ~0.55 weight → score ~45
        assert 40 <= score <= 60
        assert level in ("MEDIUM", "HIGH", "CRITICAL")


# ─── simulate_token_data tests ────────────────────────────────────────────────

class TestSimulateTokenData:
    """Tests for the simulation data generator."""

    def test_returns_tuple(self):
        """Should return (token_data, holders, lp_data)."""
        token_data, holders, lp_data = simulate_token_data()
        assert isinstance(token_data, dict)
        assert isinstance(holders, list)
        assert isinstance(lp_data, dict)

    def test_has_required_keys(self):
        """Token data should have required fields."""
        token_data, holders, lp_data = simulate_token_data()
        required = ["mint", "name", "symbol", "mintAuthority", "freezeAuthority",
                    "holderCount", "createdAt", "creatorRevealed", "flagged", "verified"]
        for key in required:
            assert key in token_data, f"Missing key: {key}"

    def test_all_scenarios_produce_valid_scores(self):
        """Run simulation many times — all should produce valid scores."""
        import random
        for _ in range(100):
            token_data, holders, lp_data = simulate_token_data()
            factors = extract_solana_risk_factors(token_data, holders, lp_data)
            score, _, level = calculate_risk_score(factors)
            assert 0 <= score <= 100
            assert level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")


# ─── Edge case tests ──────────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge cases and regression tests."""

    def test_risk_weights_sum_to_one(self):
        """Weights should sum to 1.0 (or close)."""
        total = sum(RISK_WEIGHTS.values())
        assert 0.99 <= total <= 1.01, f"Weights sum to {total}, expected ~1.0"

    def test_score_decreases_with_more_flags(self):
        """More risk flags should generally mean lower score."""
        base = {k: False for k in RISK_WEIGHTS}
        score_base, _, _ = calculate_risk_score(base)

        added = {k: False for k in RISK_WEIGHTS}
        added["mint_authority_active"] = True
        added["freeze_authority_active"] = True
        added["low_liquidity"] = True
        score_added, _, _ = calculate_risk_score(added)

        assert score_added < score_base


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
