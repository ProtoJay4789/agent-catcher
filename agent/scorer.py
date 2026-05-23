#!/usr/bin/env python3
"""
Rugcheck v2 — Solana-Native Risk Scoring Engine
=================================================
Calculates risk scores for Solana tokens based on on-chain attributes
like mint authority, freeze authority, LP lock status, holder concentration,
and creator history.

Weighted scoring system with 10 Solana-specific risk factors.
Score ranges from 0 (worst/most dangerous) to 100 (safest).

Usage:
    from scorer import extract_risk_factors, calculate_risk_score
    factors = extract_risk_factors(token_info_dict)
    score, penalty, level = calculate_risk_score(factors)
"""

from typing import Dict, List, Tuple


# ─── Risk Factor Weights (total = 1.0) ──────────────────────────────────────
# Each weight represents how much that factor contributes to the overall risk.
# Factors marked [INVERSE] penalize ABSENCE (e.g., no LP lock is bad).

RISK_WEIGHTS = {
    "has_mint_authority":       0.14,  # Can inflate supply at will = bad
    "has_freeze_authority":     0.11,  # Can freeze trades = bad
    "lp_locked":                0.16,  # [INVERSE] Locked LP = good; absence is risky
    "top_holder_concentration": 0.11,  # >50% in one wallet = bad
    "is_open_source":           0.09,  # [INVERSE] Verified program = good
    "has_social":               0.07,  # [INVERSE] Website/twitter = good
    "creator_history":          0.09,  # New/known-rug creator = riskier
    "liquidity_depth":          0.08,  # Low liquidity = riskier
    "trading_volume":           0.06,  # No volume = suspicious
    "rug_history":              0.09,  # Creator had rugs before = bad
}

# ─── Risk Classification Thresholds ─────────────────────────────────────────
# Score 0 (worst) to 100 (safest)

RISK_THRESHOLDS = {
    "LOW":      (80, 100),
    "MEDIUM":   (60, 79),
    "HIGH":     (40, 59),
    "CRITICAL": (0, 39),
}


# ─── Risk Factor Extraction ─────────────────────────────────────────────────

def extract_risk_factors(token_info: Dict) -> Dict[str, bool]:
    """
    Extract boolean risk factors from token info dict.

    Converts various data types (bool, int, str) to uniform booleans.
    Missing keys default to False (assumed safe for inverse factors,
    assumed risky for non-inverse factors — but we return False for all
    and let calculate_risk_score handle the logic).

    Args:
        token_info: Dict from BagsClient.get_token_info() containing
                    on-chain attributes of the token.

    Returns:
        Dict mapping each risk factor name to a boolean.
    """
    def _bool(val) -> bool:
        """Convert various truthy/falsy values to bool."""
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return val != 0
        if isinstance(val, str):
            return val.lower() in ("1", "true", "yes")
        return False

    # Threshold for concentration: >50% is risky
    top_holder_pct = token_info.get("top_holder_pct", 0)
    if isinstance(top_holder_pct, str):
        try:
            top_holder_pct = float(top_holder_pct)
        except ValueError:
            top_holder_pct = 0

    # Threshold for creator history: >0 rugs is risky
    creator_rug_count = token_info.get("creator_rug_count", 0)
    if isinstance(creator_rug_count, str):
        try:
            creator_rug_count = int(creator_rug_count)
        except ValueError:
            creator_rug_count = 0

    # Threshold for liquidity: <$1000 is risky
    liquidity = token_info.get("liquidity_usd", 0)
    if isinstance(liquidity, str):
        try:
            liquidity = float(liquidity)
        except ValueError:
            liquidity = 0

    # Threshold for volume: <$100 is suspicious
    volume = token_info.get("volume_24h", 0)
    if isinstance(volume, str):
        try:
            volume = float(volume)
        except ValueError:
            volume = 0

    return {
        "has_mint_authority":       _bool(token_info.get("has_mint_authority", False)),
        "has_freeze_authority":     _bool(token_info.get("has_freeze_authority", False)),
        "lp_locked":                _bool(token_info.get("lp_locked", False)),
        "top_holder_concentration": top_holder_pct > 0.50,
        "is_open_source":           _bool(token_info.get("is_open_source", False)),
        "has_social":               _bool(token_info.get("has_social", False)),
        "creator_history":          creator_rug_count > 0,
        "liquidity_depth":          liquidity < 1000,
        "trading_volume":           volume < 100,
        "rug_history":              creator_rug_count > 1,
    }


# ─── Risk Score Calculation ─────────────────────────────────────────────────

def calculate_risk_score(factors: Dict[str, bool]) -> Tuple[int, float, str]:
    """
    Calculate a risk score from 0 (worst) to 100 (safest).

    Uses weighted penalty system. Some factors are INVERSE:
    - lp_locked: True means safe (no penalty), False means risky (penalty)
    - is_open_source: True means safe (no penalty), False means risky (penalty)
    - has_social: True means safe (no penalty), False means risky (penalty)

    All other factors: True means risky (penalty), False means safe (no penalty).

    Args:
        factors: Dict of risk factor name → boolean from extract_risk_factors().

    Returns:
        Tuple of (score, total_penalty, risk_level).
        - score: int 0-100
        - total_penalty: float 0.0-1.0 (sum of weighted penalties)
        - risk_level: str ("LOW", "MEDIUM", "HIGH", or "CRITICAL")
    """
    total_penalty = 0.0

    # Inverse factors: True = safe, False = risky
    inverse_factors = {"lp_locked", "is_open_source", "has_social"}

    for factor, weight in RISK_WEIGHTS.items():
        is_flagged = factors.get(factor, False)

        if factor in inverse_factors:
            # Inverse: safe when True, risky when False
            if not is_flagged:
                total_penalty += weight
        else:
            # Normal: risky when True, safe when False
            if is_flagged:
                total_penalty += weight

    # Clamp penalty to [0, 1] and compute score
    total_penalty = max(0.0, min(1.0, total_penalty))
    score = max(0, min(100, int((1.0 - total_penalty) * 100)))

    # Classify
    level = "CRITICAL"
    for lvl, (lo, hi) in RISK_THRESHOLDS.items():
        if lo <= score <= hi:
            level = lvl
            break

    return score, total_penalty, level


# ─── Pretty Printer ──────────────────────────────────────────────────────────

def _flag(val: bool) -> str:
    """Format a risky flag."""
    return "🔴 YES" if val else "🟢 NO"

def _flag_inv(val: bool) -> str:
    """Format an inverse flag (True = good)."""
    return "🟢 YES" if val else "🔴 NO"

def _level_badge(level: str) -> str:
    """Format risk level with emoji badge."""
    badges = {
        "LOW":      "🟢 LOW",
        "MEDIUM":   "🟡 MEDIUM",
        "HIGH":     "🟠 HIGH",
        "CRITICAL": "🔴 CRITICAL",
    }
    return badges.get(level, level)


def print_results(token_info: Dict, factors: Dict[str, bool],
                  score: int, penalty: float, level: str,
                  simulated: bool = False):
    """
    Pretty-print the scan results for a token.

    Args:
        token_info: Original token info dict.
        factors: Extracted risk factors.
        score: Risk score (0-100).
        penalty: Total penalty (0.0-1.0).
        level: Risk level string.
        simulated: Whether data was simulated.
    """
    name = token_info.get("name", "N/A")
    symbol = token_info.get("symbol", "N/A")
    mint = token_info.get("mint", "N/A")
    holders = token_info.get("holders", "N/A")
    supply = token_info.get("supply", "N/A")
    creator = token_info.get("creator", "N/A")

    if creator and len(creator) > 20:
        creator = creator[:10] + "..." + creator[-8:]

    mode_tag = " [SIMULATED]" if simulated else ""

    print()
    print("=" * 60)
    print(f"  🛡️  Rugcheck — Token Risk Report{mode_tag}")
    print("=" * 60)
    print()
    print(f"  📌 Token:     {name} ({symbol})")
    print(f"  🔑 Mint:      {mint}")
    print(f"  👥 Holders:   {holders}")
    print(f"  📦 Supply:    {supply}")
    print(f"  🏷️  Creator:   {creator}")
    print()
    print("-" * 60)
    print("  📊 Risk Factors (Solana)")
    print("-" * 60)
    print(f"    Mint Authority:        {_flag(factors['has_mint_authority'])}")
    print(f"    Freeze Authority:      {_flag(factors['has_freeze_authority'])}")
    print(f"    LP Locked:             {_flag_inv(factors['lp_locked'])}")
    print(f"    >50% Holder Concentr:  {_flag(factors['top_holder_concentration'])}")
    print(f"    Open Source Program:   {_flag_inv(factors['is_open_source'])}")
    print(f"    Has Social Presence:   {_flag_inv(factors['has_social'])}")
    print(f"    Creator Rug History:   {_flag(factors['creator_history'])}")
    print(f"    Low Liquidity:         {_flag(factors['liquidity_depth'])}")
    print(f"    No Trading Volume:     {_flag(factors['trading_volume'])}")
    print(f"    Creator Multi-Rug:     {_flag(factors['rug_history'])}")
    print()
    print("-" * 60)
    print("  🎯 Risk Assessment")
    print("-" * 60)
    print(f"    Score:     {score}/100")
    print(f"    Level:     {_level_badge(level)}")
    print(f"    Penalty:   {penalty:.1%}")
    print()
    print("=" * 60)
