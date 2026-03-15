"""Disaster Recovery & Business Continuity.

Section 10.1: "A financial platform with no defined RTO and RPO
is not production-ready."

This module provides:
- Database backup and restore
- Blockchain state backup
- Recovery Time Objective (RTO) and Recovery Point Objective (RPO) tracking
- Incident response framework
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.blockchain.chain import Blockchain


class DisasterRecoveryConfig:
    """DR configuration and targets."""
    RTO_TARGET_MINUTES = 30       # Recovery Time Objective: 30 minutes
    RPO_TARGET_MINUTES = 5        # Recovery Point Objective: 5 minutes
    BACKUP_RETENTION_DAYS = 90    # Keep backups for 90 days
    BACKUP_DIR = "backups"


class BackupService:
    """Manages platform backups for disaster recovery."""

    def __init__(self, blockchain: Blockchain):
        self.blockchain = blockchain
        self.backup_dir = Path(DisasterRecoveryConfig.BACKUP_DIR)
        self.backup_dir.mkdir(exist_ok=True)

    def create_backup(self) -> dict:
        """Create a full platform backup."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"backup_{timestamp}"
        backup_path.mkdir(exist_ok=True)

        # Backup blockchain
        chain_src = Path(self.blockchain.storage_path)
        if chain_src.exists():
            shutil.copy2(chain_src, backup_path / "blockchain.json")

        # Backup database
        db_src = Path("tioli_exchange.db")
        if db_src.exists():
            shutil.copy2(db_src, backup_path / "database.db")

        # Write backup metadata
        metadata = {
            "timestamp": timestamp,
            "chain_length": self.blockchain.get_chain_info()["chain_length"],
            "chain_valid": self.blockchain.validate_chain(),
            "rto_target": f"{DisasterRecoveryConfig.RTO_TARGET_MINUTES} minutes",
            "rpo_target": f"{DisasterRecoveryConfig.RPO_TARGET_MINUTES} minutes",
        }
        (backup_path / "metadata.json").write_text(json.dumps(metadata, indent=2))

        return {
            "backup_id": timestamp,
            "path": str(backup_path),
            "chain_length": metadata["chain_length"],
            "chain_valid": metadata["chain_valid"],
            "message": "Backup created successfully",
        }

    def list_backups(self) -> list[dict]:
        """List all available backups."""
        backups = []
        if not self.backup_dir.exists():
            return backups

        for path in sorted(self.backup_dir.iterdir(), reverse=True):
            if path.is_dir() and path.name.startswith("backup_"):
                meta_file = path / "metadata.json"
                if meta_file.exists():
                    meta = json.loads(meta_file.read_text())
                    backups.append({
                        "backup_id": meta["timestamp"],
                        "chain_length": meta.get("chain_length"),
                        "chain_valid": meta.get("chain_valid"),
                    })
        return backups

    def restore_backup(self, backup_id: str) -> dict:
        """Restore from a backup.

        WARNING: This overwrites current data. Should only be
        called during disaster recovery.
        """
        backup_path = self.backup_dir / f"backup_{backup_id}"
        if not backup_path.exists():
            raise ValueError(f"Backup {backup_id} not found")

        chain_backup = backup_path / "blockchain.json"
        db_backup = backup_path / "database.db"

        restored = []
        if chain_backup.exists():
            shutil.copy2(chain_backup, self.blockchain.storage_path)
            restored.append("blockchain")
        if db_backup.exists():
            shutil.copy2(db_backup, "tioli_exchange.db")
            restored.append("database")

        return {
            "backup_id": backup_id,
            "restored": restored,
            "message": "Restore complete. Restart the application to load restored data.",
        }

    def get_dr_status(self) -> dict:
        """Get disaster recovery readiness status."""
        backups = self.list_backups()
        return {
            "rto_target": f"{DisasterRecoveryConfig.RTO_TARGET_MINUTES} minutes",
            "rpo_target": f"{DisasterRecoveryConfig.RPO_TARGET_MINUTES} minutes",
            "total_backups": len(backups),
            "latest_backup": backups[0]["backup_id"] if backups else None,
            "retention_days": DisasterRecoveryConfig.BACKUP_RETENTION_DAYS,
            "backup_directory": str(self.backup_dir),
        }


class IncidentResponsePlan:
    """Incident response protocol per Section 10.1.

    POPIA requires notification within 72 hours of a data breach.
    """

    RESPONSE_PROTOCOL = {
        "severity_levels": {
            "P1_critical": {
                "description": "Data breach, system compromise, financial loss",
                "response_time": "Immediate (within 15 minutes)",
                "notification_chain": [
                    "1. Platform owner (Stephen Endersby) — all 3 channels",
                    "2. Security team (if applicable)",
                    "3. Affected operators (within 24 hours)",
                    "4. Information Regulator (within 72 hours per POPIA)",
                ],
                "actions": [
                    "Isolate affected systems",
                    "Freeze all transactions",
                    "Capture forensic evidence",
                    "Engage incident response counsel",
                ],
            },
            "P2_high": {
                "description": "Service degradation, suspected intrusion, anomaly",
                "response_time": "Within 1 hour",
                "notification_chain": [
                    "1. Platform owner",
                    "2. Monitor for escalation to P1",
                ],
                "actions": [
                    "Investigate root cause",
                    "Enable enhanced monitoring",
                    "Prepare communications if escalation needed",
                ],
            },
            "P3_medium": {
                "description": "Performance issues, non-critical bugs, policy violations",
                "response_time": "Within 4 hours",
                "notification_chain": ["1. Platform owner (dashboard notification)"],
                "actions": ["Log incident", "Schedule fix", "Monitor"],
            },
        },
        "popia_breach_notification": {
            "deadline": "72 hours from discovery",
            "notify": "Information Regulator of South Africa",
            "content": "Nature of breach, data affected, remedial steps taken",
        },
    }

    def get_response_plan(self) -> dict:
        return self.RESPONSE_PROTOCOL
