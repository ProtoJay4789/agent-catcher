"""Tests for the Rugcheck v2 API."""

import sys
import os
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

# Ensure the api directory is on the path so imports work
_api_dir = str(Path(__file__).resolve().parent.parent)
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

from server import app, cache


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset global state between tests."""
    import server
    server.query_count = 0
    cache._cache.clear()
    cache._hits = 0
    cache._misses = 0
    yield


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# ── Health ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "2.0.0"
    assert data["mode"] == "simulation"


# ── 402 Without Payment ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_score_returns_402_without_payment(client):
    resp = await client.get("/v1/score/So11111111111111111111111111111111")
    assert resp.status_code == 402
    data = resp.json()
    assert data["error"] == "payment_required"
    assert "pricing" in data
    assert data["pricing"]["currency"] == "USDC"


# ── 200 With Payment ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_score_returns_200_with_payment(client):
    headers = {"X-Payment-Proof": "test-proof-token-abc123"}
    resp = await client.get(
        "/v1/score/So11111111111111111111111111111111",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "score" in data
    assert "level" in data
    assert "risk_factors" in data


# ── Response Shape ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_response_shape_matches_schema(client):
    headers = {"X-Payment-Proof": "proof-shape-test"}
    resp = await client.get(
        "/v1/score/So11111111111111111111111111111111",
        headers=headers,
    )
    data = resp.json()

    required_keys = {
        "mint", "score", "level", "penalty",
        "risk_factors", "token_name", "token_symbol",
        "holder_count", "lp_value",
    }
    assert required_keys.issubset(data.keys()), f"Missing keys: {required_keys - data.keys()}"
    assert isinstance(data["score"], int)
    assert 0 <= data["score"] <= 100
    assert data["level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert isinstance(data["risk_factors"], dict)


# ── Caching ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_caching_returns_same_result(client):
    headers = {"X-Payment-Proof": "proof-cache-test"}
    mint = "CacheTestMint11111111111111111111"

    resp1 = await client.get(f"/v1/score/{mint}", headers=headers)
    data1 = resp1.json()

    resp2 = await client.get(f"/v1/score/{mint}", headers=headers)
    data2 = resp2.json()

    assert data1 == data2


@pytest.mark.asyncio
async def test_caching_increases_hit_count(client):
    headers = {"X-Payment-Proof": "proof-hit-test"}
    mint = "HitTestMint11111111111111111111"

    await client.get(f"/v1/score/{mint}", headers=headers)
    stats1 = (await client.get("/v1/stats")).json()
    hits_after_first = stats1["cache"]["hits"]

    await client.get(f"/v1/score/{mint}", headers=headers)
    stats2 = (await client.get("/v1/stats")).json()
    hits_after_second = stats2["cache"]["hits"]

    assert hits_after_second > hits_after_first


# ── Stats ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stats_returns_query_count(client):
    headers = {"X-Payment-Proof": "proof-stats-test"}

    resp = await client.get("/v1/stats")
    data = resp.json()
    assert data["queries"] == 0

    await client.get("/v1/score/TestMint1", headers=headers)
    resp = await client.get("/v1/stats")
    data = resp.json()
    assert data["queries"] == 1

    await client.get("/v1/score/TestMint2", headers=headers)
    resp = await client.get("/v1/stats")
    data = resp.json()
    assert data["queries"] == 2


# ── Empty proof rejected ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_proof_rejected(client):
    resp = await client.get(
        "/v1/score/So11111111111111111111111111111111",
        headers={"X-Payment-Proof": ""},
    )
    assert resp.status_code == 402


@pytest.mark.asyncio
async def test_whitespace_proof_rejected(client):
    resp = await client.get(
        "/v1/score/So11111111111111111111111111111111",
        headers={"X-Payment-Proof": "   "},
    )
    assert resp.status_code == 402
