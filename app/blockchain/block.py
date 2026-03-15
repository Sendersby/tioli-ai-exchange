"""Block — the fundamental unit of the TiOLi blockchain ledger."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


class Block:
    """A single block in the TiOLi blockchain.

    Each block contains a list of transactions, a timestamp, the hash
    of the previous block (creating the chain), and its own hash computed
    from all of its contents — making tampering detectable.
    """

    def __init__(
        self,
        index: int,
        transactions: list[dict[str, Any]],
        previous_hash: str,
        timestamp: str | None = None,
        nonce: int = 0,
    ):
        self.index = index
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.nonce = nonce
        self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        """Generate SHA-256 hash of the block's contents."""
        block_data = json.dumps(
            {
                "index": self.index,
                "transactions": self.transactions,
                "previous_hash": self.previous_hash,
                "timestamp": self.timestamp,
                "nonce": self.nonce,
            },
            sort_keys=True,
        )
        return hashlib.sha256(block_data.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize block to dictionary for storage and API responses."""
        return {
            "index": self.index,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Block":
        """Reconstruct a block from a dictionary."""
        block = cls(
            index=data["index"],
            transactions=data["transactions"],
            previous_hash=data["previous_hash"],
            timestamp=data["timestamp"],
            nonce=data["nonce"],
        )
        block.hash = data["hash"]
        return block
