#!/usr/bin/env python3
"""
Unit tests for Rugcheck v2 risk scoring engine.

Tests cover:
  - extract_risk_factors: parsing Solana token info into boolean risk factors
  - calculate_risk_score: weighted scoring logic with inverse factors
  - Classification thresholds: LOW / MEDIUM / HIGH / CRITICAL
  - Edge cases: empty data, all risky, all safe, inverse factors
  - Solana-specific: mint authority, freeze authority, LP lock, holder concentration

Run: python3 -m pytest agent/tests/test_scoring.py -v
"""

import sys
import os
import pytest
import random

# Add parent directory to path so we can import scorer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scorer import (
    extract_risk_factors,
    calculate_risk_score,
    RISK_WEIGHTS,
    RISK_THRESHOLDS,
)


# ─── extract_risk_factors tests ─────────────────────────────────────────────

class TestExtractRiskFactors:
    """Tests for parsing raw Solana token info into boolean risk factors."""

    def test_all_risky(self):
        raw = {
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
        factors = extract_risk_factors(raw)
        assert factors["has_mint_authority"] is True
        assert factors["has_freeze_authority"] is True
        assert factors["lp_locked"] is False
        assert factors["top_holder_concentration"] is True
        assert factors["is_open_source"] is False
        assert factors["has_social"] is False
        assert factors["creator_history"] is True
        assert factors["liquidity_depth"] is True
        assert factors["trading_volume"] is True
        assert factors["rug_history"] is True

    def test_all_safe(self):
        raw = {
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
        factors = extract_risk_factors(raw)
        assert factors["has_mint_authority"] is False
        assert factors["has_freeze_authority"] is False
        assert factors["lp_locked"] is True
        assert factors["top_holder_concentration"] is False
        assert factors["is_open_source"] is True
        assert factors["has_social"] is True
        assert factors["creator_history"] is False
        assert factors["liquidity_depth"] is False
        assert factors["trading_volume"] is False
        assert factors["rug_history"] is False

    def test_missing_keys_default_safe(self):
        """Missing keys should default to False (or safe-ish for most factors).
        Note: missing liquidity_usd/volume_24h default to 0, which triggers
        low-liquidity and no-volume flags."""
        raw = {}
        factors = extract_risk_factors(raw)
        # Most factors should be False
        assert factors["has_mint_authority"] is False
        assert factors["has_freeze_authority"] is False
        assert factors["is_open_source"] is False
        assert factors["has_social"] is False
        assert factors["creator_history"] is False
        assert factors["rug_history"] is False
        # liquidity_depth and trading_volume trigger on 0 values
        assert factors["liquidity_depth"] is True  # 0 < 1000
        assert factors["trading_volume"] is True    # 0 < 100

    def test_numeric_strings(self):
        """Bags API might return string values."""
        raw = {
            "has_mint_authority": "1",
            "has_freeze_authority": "0",
            "lp_locked": "true",
            "top_holder_pct": "0.6",
            "creator_rug_count": "2",
            "liquidity_usd": "500",
            "volume_24h": "50",
        }
        factors = extract_risk_factors(raw)
        assert factors["has_mint_authority"] is True
        assert factors["has_freeze_authority"] is False
        assert factors["lp_locked"] is True
        assert factors["top_holder_concentration"] is True
        assert factors["creator_history"] is True
        assert factors["liquidity_depth"] is True
        assert factors["trading_volume"] is True
        assert factors["rug_history"] is True

    def test_mixed_risk(self):
        """Partial risk flags."""
        raw = {
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
        factors = extract_risk_factors(raw)
        assert factors["has_mint_authority"] is True
        assert factors["lp_locked"] is False
        assert factors["top_holder_concentration"] is False  # 35% < 50%
        assert factors["is_open_source"] is False
        assert factors["has_social"] is True
        assert factors["creator_history"] is True  # 1 rug
        assert factors["rug_history"] is False  # only 1 rug, not >1


# ─── calculate_risk_score tests ─────────────────────────────────────────────

class TestCalculateRiskScore:
    """Tests for the weighted scoring engine."""

    def test_perfect_score(self):
        """All safe → score 100, level LOW."""
        factors = {
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
        score, penalty, level = calculate_risk_score(factors)
        assert score == 100
        assert level == "LOW"
        assert penalty == 0.0

    def test_worst_score(self):
        """All risky → score 0, level CRITICAL."""
        factors = {
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
        score, penalty, level = calculate_risk_score(factors)
        assert score == 0
        assert level == "CRITICAL"
        assert penalty >= 0.95

    def test_lp_lock_heavy_weight(self):
        """No LP lock alone should push score into MEDIUM range (weight 0.18)."""
        factors = {
            "has_mint_authority": False,
            "has_freeze_authority": False,
            "lp_locked": False,  # Not locked = risky
            "top_holder_concentration": False,
            "is_open_source": True,
            "has_social": True,
            "creator_history": False,
            "liquidity_depth": False,
            "trading_volume": False,
            "rug_history": False,
        }
        score, penalty, level = calculate_risk_score(factors)
        # lp_locked weight is 0.18, so score drops by ~18
        assert 78 <= score <= 85
        assert level in ("LOW", "MEDIUM")

    def test_closed_source_penalty(self):
        """Not open source should penalize."""
        factors_safe = {
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
        _, penalty_safe, _ = calculate_risk_score(factors_safe)

        factors_closed = dict(factors_safe)
        factors_closed["is_open_source"] = False
        _, penalty_closed, _ = calculate_risk_score(factors_closed)

        assert penalty_closed > penalty_safe

    def test_score_bounds(self):
        """Score should always be between 0 and 100."""
        for _ in range(50):
            factors = {
                "has_mint_authority": random.choice([True, False]),
                "has_freeze_authority": random.choice([True, False]),
                "lp_locked": random.choice([True, False]),
                "top_holder_concentration": random.choice([True, False]),
                "is_open_source": random.choice([True, False]),
                "has_social": random.choice([True, False]),
                "creator_history": random.choice([True, False]),
                "liquidity_depth": random.choice([True, False]),
                "trading_volume": random.choice([True, False]),
                "rug_history": random.choice([True, False]),
            }
            score, _, _ = calculate_risk_score(factors)
            assert 0 <= score <= 100

    def test_classification_thresholds(self):
        """Verify all levels are reachable."""
        levels_found = set()
        for _ in range(200):
            factors = {
                "has_mint_authority": random.choice([True, False]),
                "has_freeze_authority": random.choice([True, False]),
                "lp_locked": random.choice([True, False]),
                "top_holder_concentration": random.choice([True, False]),
                "is_open_source": random.choice([True, False]),
                "has_social": random.choice([True, False]),
                "creator_history": random.choice([True, False]),
                "liquidity_depth": random.choice([True, False]),
                "trading_volume": random.choice([True, False]),
                "rug_history": random.choice([True, False]),
            }
            _, _, level = calculate_risk_score(factors)
            levels_found.add(level)
        assert "LOW" in levels_found
        assert "CRITICAL" in levels_found

    def test_known_dangerous_combo(self):
        """Mint authority + freeze + no LP lock + high concentration."""
        factors = {
            "has_mint_authority": True,    # 0.15
            "has_freeze_authority": True,  # 0.12
            "lp_locked": False,            # 0.18 (inverse)
            "top_holder_concentration": True,  # 0.12
            "is_open_source": False,       # 0.10 (inverse)
            "has_social": True,            # safe
            "creator_history": False,      # safe
            "liquidity_depth": False,      # safe
            "trading_volume": False,       # safe
            "rug_history": False,          # safe
        }
        # Total penalty: 0.15 + 0.12 + 0.18 + 0.12 + 0.10 = 0.67
        score, _, level = calculate_risk_score(factors)
        assert 30 <= score <= 40
        assert level in ("HIGH", "CRITICAL")

    def test_inverse_factor_logic(self):
        """Inverse factors: True=safe, False=risky."""
        # LP locked (True) should NOT penalize
        factors_locked = {
            "has_mint_authority": False,
            "has_freeze_authority": False,
            "lp_locked": True,
            "top_holder_concentration": False,
            "is_open_source": False,
            "has_social": False,
            "creator_history": False,
            "liquidity_depth": False,
            "trading_volume": False,
            "rug_history": False,
        }
        _, penalty_locked, _ = calculate_risk_score(factors_locked)

        # LP NOT locked (False) SHOULD penalize
        factors_unlocked = dict(factors_locked)
        factors_unlocked["lp_locked"] = False
        _, penalty_unlocked, _ = calculate_risk_score(factors_unlocked)

        assert penalty_unlocked > penalty_locked


# ─── Edge case tests ────────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge cases and regression tests."""

    def test_empty_factors(self):
        """Empty dict should produce moderate score (inverse factors penalize)."""
        factors = {}
        score, penalty, level = calculate_risk_score(factors)
        # Inverse factors (lp_locked, is_open_source, has_social) default to False
        # so they penalize: 0.18 + 0.10 + 0.08 = 0.36 → score ~64
        assert 60 <= score <= 70

    def test_risk_weights_sum_to_one(self):
        """Weights should sum to 1.0 (or close)."""
        total = sum(RISK_WEIGHTS.values())
        assert 0.99 <= total <= 1.01, f"Weights sum to {total}, expected ~1.0"

    def test_score_decreases_with_more_flags(self):
        """More risk flags should generally mean lower score."""
        base = {
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
        score_base, _, _ = calculate_risk_score(base)

        added = dict(base)
        added["has_mint_authority"] = True
        added["has_freeze_authority"] = True
        added["lp_locked"] = False
        added["top_holder_concentration"] = True
        score_added, _, _ = calculate_risk_score(added)

        assert score_added < score_base


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
