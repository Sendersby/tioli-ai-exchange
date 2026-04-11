"""Blockchain — the immutable, transparent ledger for TiOLi AGENTIS."""

import json
import threading
from pathlib import Path
from typing import Any

from app.blockchain.block import Block
from app.blockchain.transaction import Transaction, TransactionStatus


class Blockchain:
    """The TiOLi blockchain: an append-only, tamper-evident ledger.

    Every transaction on the platform is recorded here permanently.
    The chain can be validated at any time to prove no data has been
    altered — providing the 100% transparency required by the brief.
    """

    DIFFICULTY = 2  # Number of leading zeros required in block hash

    def __init__(self, storage_path: str = "blockchain_data.json"):
        self._lock = threading.Lock()
        self.storage_path = Path(storage_path)
        self.chain: list[Block] = []
        self.pending_transactions: list[dict[str, Any]] = []

        # Ensure parent directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        if self.storage_path.exists():
            self._load_chain()
            # Startup verification: validate chain integrity
            if not self.validate_chain():
                import logging
                logging.getLogger(__name__).error(
                    "Blockchain integrity check FAILED on startup"
                )
        else:
            self._create_genesis_block()
            # Verify genesis was persisted
            if not self.storage_path.exists():
                raise RuntimeError(
                    f"Failed to create blockchain file at {self.storage_path}"
                )

    def _create_genesis_block(self) -> None:
        """Create the first block in the chain — the foundation."""
        genesis = Block(
            index=0,
            transactions=[{
                "type": "genesis",
                "description": "TiOLi AGENTIS — Genesis Block. "
                "For the ultimate good of Humanity, Agents, and Agentic operators.",
                "founder": "Stephen Endersby",
                "company": "TiOLi Group Holdings (Pty) Ltd",
            }],
            previous_hash="0" * 64,
        )
        self.chain.append(genesis)
        self._save_chain()

    def add_transaction(self, transaction: Transaction) -> str:
        """Add a confirmed transaction to the pending pool.

        Returns the transaction ID for tracking.
        """
        transaction.status = TransactionStatus.CONFIRMED
        ledger_entry = transaction.to_ledger_entry()

        with self._lock:
            self.pending_transactions.append(ledger_entry)

            # Auto-mine a new block every 10 transactions or on demand
            if len(self.pending_transactions) >= 10:
                self.mine_block()

        return transaction.id

    def mine_block(self) -> Block | None:
        """Mine pending transactions into a new block on the chain."""
        with self._lock:
            if not self.pending_transactions:
                return None

            last_block = self.chain[-1]
            new_block = Block(
                index=len(self.chain),
                transactions=list(self.pending_transactions),
                previous_hash=last_block.hash,
            )

            # Proof of work — find a nonce that produces a hash with
            # the required number of leading zeros
            new_block = self._proof_of_work(new_block)

            self.chain.append(new_block)
            self.pending_transactions.clear()
            self._save_chain()
            return new_block

    def _proof_of_work(self, block: Block) -> Block:
        """Simple proof-of-work: increment nonce until hash meets difficulty."""
        target = "0" * self.DIFFICULTY
        while not block.hash.startswith(target):
            block.nonce += 1
            block.hash = block.compute_hash()
        return block

    def validate_chain(self) -> bool:
        """Verify the entire blockchain is intact and untampered.

        Checks:
        1. Each block's hash matches its computed hash
        2. Each block's previous_hash matches the prior block's hash
        3. Each block meets the proof-of-work difficulty requirement
        """
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            # Verify hash integrity
            if current.hash != current.compute_hash():
                return False

            # Verify chain linkage
            if current.previous_hash != previous.hash:
                return False

            # Verify proof of work
            if not current.hash.startswith("0" * self.DIFFICULTY):
                return False

        return True

    def get_transactions_for_agent(self, agent_id: str) -> list[dict[str, Any]]:
        """Retrieve all transactions involving a specific agent."""
        results = []
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("sender_id") == agent_id or tx.get("receiver_id") == agent_id:
                    results.append(tx)
        # Also check pending
        for tx in self.pending_transactions:
            if tx.get("sender_id") == agent_id or tx.get("receiver_id") == agent_id:
                results.append(tx)
        return results

    def get_all_transactions(self) -> list[dict[str, Any]]:
        """Return every transaction ever recorded — full transparency.

        AUD-11 fix: includes confirmation_status metadata.
        """
        results = []
        for block in self.chain:
            for tx in block.transactions:
                tx_copy = dict(tx)
                tx_copy["confirmation_status"] = "CONFIRMED"
                tx_copy["block_hash"] = block.hash
                tx_copy["block_index"] = block.index
                results.append(tx_copy)
        # Include pending with PENDING status
        for tx in self.pending_transactions:
            tx_copy = dict(tx)
            tx_copy["confirmation_status"] = "PENDING"
            tx_copy["block_hash"] = None
            tx_copy["block_index"] = None
            results.append(tx_copy)
        return results

    def get_chain_info(self) -> dict[str, Any]:
        """Platform-level blockchain statistics."""
        all_tx = self.get_all_transactions()
        return {
            "chain_length": len(self.chain),
            "total_transactions": len(all_tx),
            "pending_transactions": len(self.pending_transactions),
            "is_valid": self.validate_chain(),
            "latest_block_hash": self.chain[-1].hash if self.chain else None,
        }

    def force_mine(self) -> Block | None:
        """Force-mine any pending transactions into a block immediately."""
        return self.mine_block()

    def _save_chain(self) -> None:
        """Persist the blockchain to disk (atomic write — crash-safe).

        Writes to a temp file first, then renames. This ensures the chain
        file is never in a partially-written state if the process crashes.
        """
        import tempfile
        data = {
            "chain": [block.to_dict() for block in self.chain],
            "pending": self.pending_transactions,
        }
        content = json.dumps(data, indent=2)
        # Write to temp file in same directory, then atomic rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.storage_path.parent),
            suffix=".tmp",
        )
        try:
            with open(fd, 'w') as f:
                f.write(content)
            # Atomic rename (POSIX guarantees this is atomic on same filesystem)
            import shutil
            shutil.move(tmp_path, str(self.storage_path))
            # Verify write succeeded (file size grew or stayed consistent)
            if not self.storage_path.exists():
                raise RuntimeError("Blockchain file missing after save")
        except Exception as e:
            # Clean up temp file on failure
            import os
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _load_chain(self) -> None:
        """Load the blockchain from disk."""
        data = json.loads(self.storage_path.read_text())
        self.chain = [Block.from_dict(b) for b in data["chain"]]
        self.pending_transactions = data.get("pending", [])
