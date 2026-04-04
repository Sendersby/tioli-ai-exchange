"""Arch Agent Credential Vault — AES-256-GCM encryption.

Zero plaintext: no credential ever exists in plaintext outside this vault.
All encryption uses AES-256-GCM with PBKDF2-derived keys.
Every access is logged in arch_audit_log (enforced at application layer).
"""

import logging
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("arch.vault")


class CredentialVault:
    """AES-256-GCM credential vault for Arch Agent external accounts."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        raw_key = os.getenv("ARCH_VAULT_ENCRYPTION_KEY", "")
        if not raw_key:
            raise EnvironmentError("ARCH_VAULT_ENCRYPTION_KEY must be set")
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"agentis_vault_v1",
            iterations=100_000,
        )
        self.key = kdf.derive(raw_key.encode())

    def _encrypt(self, plaintext: str) -> tuple[bytes, bytes]:
        """Returns (ciphertext, iv) — store both in DB."""
        iv = secrets.token_bytes(12)
        aesgcm = AESGCM(self.key)
        ct = aesgcm.encrypt(iv, plaintext.encode(), None)
        return ct, iv

    def _decrypt(self, ciphertext: bytes, iv: bytes) -> str:
        """Decrypt ciphertext with the stored IV."""
        aesgcm = AESGCM(self.key)
        return aesgcm.decrypt(iv, ciphertext, None).decode()

    async def store(
        self,
        db: AsyncSession,
        platform: str,
        account_type: str = "brand",
        email: str = None,
        username: str = None,
        password: str = None,
        api_key: str = None,
        token: str = None,
    ) -> str:
        """Encrypts and stores credentials. Returns vault entry ID."""

        def enc(val):
            return self._encrypt(val) if val else (None, None)

        # Use a single IV for all fields in one entry
        iv = secrets.token_bytes(12)
        aesgcm = AESGCM(self.key)

        def enc_with_iv(val):
            if not val:
                return None
            return aesgcm.encrypt(iv, val.encode(), None)

        email_ct = enc_with_iv(email)
        user_ct = enc_with_iv(username)
        pass_ct = enc_with_iv(password)
        key_ct = enc_with_iv(api_key)
        tok_ct = enc_with_iv(token)

        rotation_days = int(os.getenv("ARCH_CREDENTIAL_ROTATION_DAYS_API", "90"))

        result = await db.execute(
            text("""
                INSERT INTO arch_credential_vault
                    (agent_id, platform, account_email_enc, username_enc,
                     password_enc, api_key_enc, token_enc, iv,
                     rotation_due_at)
                VALUES (
                    (SELECT id FROM arch_agents WHERE agent_name = :agent_id),
                    :platform, :email_ct, :user_ct,
                    :pass_ct, :key_ct, :tok_ct, :iv,
                    now() + make_interval(days => :rotation_days)
                )
                RETURNING id::text
            """),
            {
                "agent_id": self.agent_id,
                "platform": platform,
                "email_ct": email_ct,
                "user_ct": user_ct,
                "pass_ct": pass_ct,
                "key_ct": key_ct,
                "tok_ct": tok_ct,
                "iv": iv,
                "rotation_days": rotation_days,
            },
        )
        await db.commit()
        return result.scalar()

    async def retrieve(self, db: AsyncSession, platform: str) -> dict:
        """Retrieves and decrypts credentials for a platform."""
        row_result = await db.execute(
            text("""
                SELECT id, account_email_enc, username_enc, password_enc,
                       api_key_enc, token_enc, iv
                FROM arch_credential_vault
                WHERE agent_id = (SELECT id FROM arch_agents WHERE agent_name = :agent_id)
                  AND platform = :platform
                ORDER BY created_at DESC LIMIT 1
            """),
            {"agent_id": self.agent_id, "platform": platform},
        )
        r = row_result.fetchone()
        if not r:
            return {}

        iv = r.iv

        def dec(ct):
            return self._decrypt(ct, iv) if ct else None

        # Update last_used_at
        await db.execute(
            text("UPDATE arch_credential_vault SET last_used_at = now() WHERE id = :id"),
            {"id": r.id},
        )
        await db.commit()

        return {
            "email": dec(r.account_email_enc),
            "username": dec(r.username_enc),
            "password": dec(r.password_enc),
            "api_key": dec(r.api_key_enc),
            "token": dec(r.token_enc),
        }
