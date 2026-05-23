"""Rugcheck v2 API — FastAPI server for Solana token risk scores.

Serves risk scores via x402 micropayments. Uses simulation mode by default.
"""

import sys
import os
from pathlib import Path
from contextlib import asynccontextmanager

# Add agent directory to path for scoring engine imports
_agent_dir = str(Path(__file__).resolve().parent.parent / "agent")
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from cache import ScoreCache
from payment import PaymentVerifier
from bags_scanner import (
    extract_solana_risk_factors,
    calculate_risk_score,
    simulate_token_data,
    RISK_WEIGHTS,
    RISK_THRESHOLDS,
)

# ─── State ────────────────────────────────────────────────────────────────────

cache = ScoreCache(ttl_seconds=300)
verifier = PaymentVerifier()
query_count = 0


# ─── App ──────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(
    title="Rugcheck v2 API",
    description="Solana token risk scoring via x402 micropayments",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

PAYMENT_REQUIRED_BODY = {
    "error": "payment_required",
    "message": "X-Payment-Proof header required. Pay to receive a risk score.",
    "pricing": {
        "amount": "0.01",
        "currency": "USDC",
        "network": "solana",
    },
}


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/v1/health")
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "mode": "simulation",
    }


@app.get("/v1/stats")
async def stats():
    return {
        "queries": query_count,
        "cache": cache.stats(),
        "payments_verified": verifier.payment_count(),
    }


@app.get("/v1/score/{mint_address}")
async def score(mint_address: str, request: Request, response: Response):
    global query_count

    # Check payment proof
    proof = request.headers.get("X-Payment-Proof")
    if not verifier.verify(proof):
        response.status_code = 402
        return PAYMENT_REQUIRED_BODY

    query_count += 1

    # Check cache
    cached = cache.get(mint_address)
    if cached is not None:
        return cached

    # Compute score (simulation mode)
    token_data, holders, lp_data = simulate_token_data(mint_address)
    factors = extract_solana_risk_factors(token_data, holders, lp_data)
    score_val, penalty, level = calculate_risk_score(factors)

    result = {
        "mint": mint_address,
        "score": score_val,
        "level": level,
        "penalty": round(penalty, 4),
        "risk_factors": factors,
        "token_name": token_data.get("name", "Unknown"),
        "token_symbol": token_data.get("symbol", "???"),
        "holder_count": token_data.get("holderCount", 0),
        "lp_value": lp_data.get("totalValueLocked", 0),
    }

    cache.set(mint_address, result)
    return result
