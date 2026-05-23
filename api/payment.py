"""x402 micropayment verification module.

For MVP: accepts any non-empty X-Payment-Proof header.
Real on-chain verification comes later.
"""

from typing import Dict, Optional
import time


class PaymentVerifier:
    """Handles x402/MPP payment proof verification."""

    def __init__(self):
        self._payments: Dict[str, Dict] = {}

    def verify(self, proof_header: Optional[str]) -> bool:
        """Verify a payment proof. MVP: accept any non-empty string."""
        if not proof_header or not proof_header.strip():
            return False
        # Store the payment record
        token = proof_header.strip()
        self._payments[token] = {
            "verified_at": time.time(),
            "token": token,
        }
        return True

    def payment_count(self) -> int:
        return len(self._payments)
