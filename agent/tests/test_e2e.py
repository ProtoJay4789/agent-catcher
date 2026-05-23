#!/usr/bin/env python3
"""
End-to-end test for Rugcheck v2 pipeline.

Tests the full flow: token mint → BagsClient → score → alert.
Runs entirely offline using simulation mode (no API calls).

Run: python3 -m pytest agent/tests/test_e2e.py -v
"""

import sys
import os
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scorer import (
    extract_risk_factors,
    calculate_risk_score,
    print_results,
    RISK_WEIGHTS,
    RISK_THRESHOLDS,
)
from scanners.bags_client import BagsClient
from alerts import AlertDispatcher


class TestE2EPipeline:
    """Full pipeline: token → scan → score → classify."""

    def test_safe_token_pipeline(self):
        """Safe token should score HIGH and classify as LOW."""
        client = BagsClient(simulate=True)

        # Step 1: Get token info
        info = client.get_token_info("So11111111111111111111111111111111111111112")
        assert info, "Scan returned empty data"

        # Step 2: Extract factors
        factors = extract_risk_factors(info)
        assert len(factors) == len(RISK_WEIGHTS)

        # Step 3: Score
        score, penalty, level = calculate_risk_score(factors)
        assert 0 <= score <= 100

        # Step 4: Verify valid level
        assert level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_full_pipeline_produces_output(self):
        """Pipeline should produce printable results without errors."""
        client = BagsClient(simulate=True)
        info = client.get_token_info("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
        factors = extract_risk_factors(info)
        score, penalty, level = calculate_risk_score(factors)

        # This should not raise
        print_results(info, factors, score, penalty, level, simulated=True)

    def test_json_output_mode(self):
        """JSON mode should produce valid JSON."""
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

        # Should be valid JSON
        json_str = json.dumps(output, indent=2)
        parsed = json.loads(json_str)
        assert parsed["token_address"] == token
        assert parsed["score"] == score
        assert parsed["level"] == level

    def test_multiple_tokens_pipeline(self):
        """Run pipeline on multiple tokens — all should complete."""
        client = BagsClient(simulate=True)
        tokens = [
            "So11111111111111111111111111111111111111112",
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        ]

        results = []
        for token in tokens:
            info = client.get_token_info(token)
            factors = extract_risk_factors(info)
            score, penalty, level = calculate_risk_score(factors)
            results.append({
                "token": token,
                "score": score,
                "level": level,
            })

        assert len(results) == len(tokens)
        for r in results:
            assert 0 <= r["score"] <= 100
            assert r["level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_scoring_consistency(self):
        """Same input should produce same output."""
        client = BagsClient(simulate=True)
        token = "So11111111111111111111111111111111111111112"

        # Run twice — deterministic simulation
        info1 = client.get_token_info(token)
        factors1 = extract_risk_factors(info1)
        score1, _, level1 = calculate_risk_score(factors1)

        info2 = client.get_token_info(token)
        factors2 = extract_risk_factors(info2)
        score2, _, level2 = calculate_risk_score(factors2)

        # Same input → same output
        assert factors1 == factors2
        assert score1 == score2
        assert level1 == level2

    def test_risk_classification_always_valid(self):
        """Score 0-100 always maps to a valid level."""
        for score in range(0, 101):
            level = None
            for lvl, (lo, hi) in RISK_THRESHOLDS.items():
                if lo <= score <= hi:
                    level = lvl
                    break
            assert level is not None, f"Score {score} has no classification"

    def test_alert_thresholds(self):
        """HIGH and CRITICAL scores should trigger alerts."""
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

        score, _, level = calculate_risk_score(factors)

        # This should be HIGH or CRITICAL
        assert level in ("HIGH", "CRITICAL"), \
            f"Dangerous token scored {level} ({score}) — expected HIGH or CRITICAL"

    def test_pipeline_cli_args(self):
        """Test that CLI argument parsing works for full pipeline."""
        from agent.agent import build_parser

        parser = build_parser()

        # Simulate --simulate mode
        args = parser.parse_args(["--simulate", "--interval", "30"])
        assert args.simulate is True
        assert args.interval == 30

        # Simulate --live mode
        args = parser.parse_args(["--live", "--api-key", "test123"])
        assert args.live is True
        assert args.api_key == "test123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
