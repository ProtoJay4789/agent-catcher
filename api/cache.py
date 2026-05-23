"""Score caching module with TTL-based expiration."""

import time
from typing import Any, Dict, Optional


class ScoreCache:
    """TTL-based cache for risk scores."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._hits = 0
        self._misses = 0

    def get(self, mint: str) -> Optional[Dict[str, Any]]:
        """Return cached score data or None if expired/missing."""
        entry = self._cache.get(mint)
        if entry is None:
            self._misses += 1
            return None
        if time.time() - entry["timestamp"] > self.ttl:
            del self._cache[mint]
            self._misses += 1
            return None
        self._hits += 1
        return entry["data"]

    def set(self, mint: str, score_data: Dict[str, Any]) -> None:
        """Store score data with current timestamp."""
        self._cache[mint] = {
            "data": score_data,
            "timestamp": time.time(),
        }

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        return {
            "hits": self._hits,
            "misses": self._misses,
            "entries": len(self._cache),
            "hit_rate": (
                round(self._hits / (self._hits + self._misses), 4)
                if (self._hits + self._misses) > 0
                else 0.0
            ),
        }
