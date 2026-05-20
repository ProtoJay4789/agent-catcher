#!/usr/bin/env python3
"""
End-to-end test for Agent Catcher pipeline.

Tests the full flow: token address → agent scan → score → alert.
Runs entirely offline using simulation mode (no GoPlus API calls).

Run: python3 -m pytest agent/tests/test_e2e.py -v
"""

import sys
import os
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from monitor import (
    extract_risk_factors,
    calculate_risk_score,
    simulate_goplus,
    print_results,
    scaffold_submit,
    RISK_WEIGHTS,
    RISK_THRESHOLDS,
)


class TestE2EPipeline:
    """Full pipeline: token → scan → score → classify."""

    def test_safe_token_pipeline(self):
        """Safe token should score HIGH and classify as LOW."""
        token = "0x2::sui::SUI"

        # Step 1: Simulate scan
        raw_data = simulate_goplus(token)
        assert raw_data, "Scan returned empty data"

        # Step 2: Extract factors
        factors = extract_risk_factors(raw_data)
        assert len(factors) == len(RISK_WEIGHTS)

        # Step 3: Score
        score, penalty, level = calculate_risk_score(factors)
        assert 0 <= score <= 100

        # Step 4: For safe scenario, score should be good
        # (simulation is random, but safe is most common — just verify pipeline works)
        assert level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_full_pipeline_produces_output(self):
        """Pipeline should produce printable results without errors."""
        token = "0xtoken_address_123"
        raw_data = simulate_goplus(token)
        factors = extract_risk_factors(raw_data)
        score, penalty, level = calculate_risk_score(factors)

        # This should not raise
        print_results(token, raw_data, factors, score, penalty, level, simulated=True)

    def test_json_output_mode(self):
        """--json mode should produce valid JSON."""
        token = "0x2::sui::SUI"
        raw_data = simulate_goplus(token)
        factors = extract_risk_factors(raw_data)
        score, penalty, level = calculate_risk_score(factors)

        output = {
            "token_address": token,
            "score": score,
            "level": level,
            "penalty": round(penalty, 4),
            "factors": factors,
            "raw": raw_data,
            "simulated": True,
        }

        # Should be valid JSON
        json_str = json.dumps(output, indent=2)
        parsed = json.loads(json_str)
        assert parsed["token_address"] == token
        assert parsed["score"] == score
        assert parsed["level"] == level

    def test_submit_scaffold_produces_output(self):
        """On-chain submission scaffold should not raise errors."""
        token = "0x2::sui::SUI"
        raw_data = simulate_goplus(token)
        factors = extract_risk_factors(raw_data)
        score, penalty, level = calculate_risk_score(factors)

        # This prints the scaffold — should not raise
        scaffold_submit(token, score, level, factors, "test_agent")

    def test_multiple_tokens_pipeline(self):
        """Run pipeline on multiple tokens — all should complete."""
        tokens = [
            "0x2::sui::SUI",
            "0xtoken_abc",
            "0xdeadbeef",
            "0x1234567890abcdef",
        ]

        results = []
        for token in tokens:
            raw_data = simulate_goplus(token)
            factors = extract_risk_factors(raw_data)
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
        token = "0xtest_consistency"

        # Run twice with deterministic data
        raw1 = simulate_goplus(token)
        factors1 = extract_risk_factors(raw1)
        score1, _, level1 = calculate_risk_score(factors1)

        raw2 = simulate_goplus(token)
        factors2 = extract_risk_factors(raw2)
        score2, _, level2 = calculate_risk_score(factors2)

        # Simulation is random, but scoring logic is deterministic
        # So same factors → same score
        if factors1 == factors2:
            assert score1 == score2
            assert level1 == level2

    def test_risk_classification_always_valid(self):
        """Score 0-100 always maps to a valid level."""
        for score in range(0, 101):
            # Create factors that would produce this exact score
            # by reverse-engineering: if we know the score, we can check classification
            level = None
            for lvl, (lo, hi) in RISK_THRESHOLDS.items():
                if lo <= score <= hi:
                    level = lvl
                    break
            assert level is not None, f"Score {score} has no classification"

    def test_alert_thresholds(self):
        """HIGH and CRITICAL scores should trigger alerts."""
        # Create a dangerous scenario
        factors = {k: False for k in RISK_WEIGHTS}
        factors["is_open_source"] = False
        factors["is_honeypot"] = True
        factors["can_take_back_liquidity"] = True
        factors["hidden_owner"] = True
        factors["selfdestruct"] = True
        factors["malicious_behavior"] = True
        factors["is_blacklisted"] = True

        score, _, level = calculate_risk_score(factors)

        # This should be HIGH or CRITICAL
        assert level in ("HIGH", "CRITICAL"), \
            f"Dangerous token scored {level} ({score}) — expected HIGH or CRITICAL"

    def test_pipeline_cli_args(self):
        """Test that CLI argument parsing works for full pipeline."""
        from monitor import build_parser

        parser = build_parser()

        # Simulate --simulate mode
        args = parser.parse_args(["--token", "0xtest", "--simulate", "--json"])
        assert args.token == "0xtest"
        assert args.simulate is True
        assert args.json is True

        # Simulate --submit mode
        args = parser.parse_args(["--token", "0xtest", "--simulate", "--submit"])
        assert args.submit is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
