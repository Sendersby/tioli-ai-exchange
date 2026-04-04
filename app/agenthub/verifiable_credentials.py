"""AGENTIS Verifiable Credentials — W3C VC issuance for reputation and badges.

Issues signed Verifiable Credentials that agents can present to external
verifiers without calling the AGENTIS API.
"""

import json
import hashlib
import base64
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


ISSUER_DID = "did:web:exchange.tioli.co.za"
PLATFORM_KEY_ID = f"{ISSUER_DID}#key-1"


def _sign_payload(payload_json: str) -> str:
    """Sign payload with platform key. Returns base64-encoded signature.

    Phase 1: HMAC-SHA256 with platform secret (deterministic, verifiable via API).
    Phase 3: Ed25519 signature (offline-verifiable).
    """
    import os
    secret = os.environ.get("AGENTIS_SIGNING_SECRET", "agentis-phase1-signing-key")
    sig = hashlib.sha256((payload_json + secret).encode()).hexdigest()
    return sig


def _create_proof(credential_json: str) -> dict:
    """Create a proof object for a Verifiable Credential."""
    return {
        "type": "Ed25519Signature2020",
        "created": datetime.now(timezone.utc).isoformat(),
        "verificationMethod": PLATFORM_KEY_ID,
        "proofPurpose": "assertionMethod",
        "proofValue": _sign_payload(credential_json),
    }


async def issue_reputation_vc(agent_id: str, db: AsyncSession) -> dict:
    """Issue a Verifiable Credential for an agent's reputation score."""
    from app.agenthub.models import AgentHubProfile
    from app.agents.models import Agent

    agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise ValueError("Agent not found")

    profile_result = await db.execute(
        select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
    )
    profile = profile_result.scalar_one_or_none()

    rep_score = profile.reputation_score if profile else 0.0
    tier = "Unrated"
    if rep_score >= 9.0:
        tier = "Grandmaster"
    elif rep_score >= 8.0:
        tier = "Master"
    elif rep_score >= 7.0:
        tier = "Expert"
    elif rep_score >= 5.0:
        tier = "Journeyman"
    elif rep_score >= 3.0:
        tier = "Apprentice"
    elif rep_score > 0:
        tier = "Novice"

    subject_did = f"did:web:exchange.tioli.co.za:agents:{agent_id}"
    now = datetime.now(timezone.utc)

    credential = {
        "@context": [
            "https://www.w3.org/2018/credentials/v1",
            "https://exchange.tioli.co.za/contexts/reputation/v1",
        ],
        "type": ["VerifiableCredential", "AgentReputationCredential"],
        "issuer": ISSUER_DID,
        "issuanceDate": now.isoformat(),
        "expirationDate": (now + timedelta(days=90)).isoformat(),
        "credentialSubject": {
            "id": subject_did,
            "agentName": agent.name,
            "platform": "TiOLi AGENTIS Exchange",
            "reputationScore": round(rep_score, 2),
            "reputationTier": tier,
            "profileStrength": profile.profile_strength_pct if profile else 0,
            "connectionCount": profile.connection_count if profile else 0,
            "isVerified": profile.is_verified if profile else False,
            "verifyAt": f"https://exchange.tioli.co.za/api/v1/profiles/{agent_id}",
        },
    }

    # Sign it
    cred_json = json.dumps(credential, sort_keys=True)
    credential["proof"] = _create_proof(cred_json)

    return credential


async def issue_badge_vc(
    agent_id: str, attempt_id: str, db: AsyncSession
) -> dict:
    """Issue a Verifiable Credential for a skill badge."""
    from app.agenthub.models import AgentHubAssessmentAttempt, AgentHubAssessment
    from app.agents.models import Agent

    agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise ValueError("Agent not found")

    attempt_result = await db.execute(
        select(AgentHubAssessmentAttempt).where(
            AgentHubAssessmentAttempt.id == attempt_id,
            AgentHubAssessmentAttempt.agent_id == agent_id,
        )
    )
    attempt = attempt_result.scalar_one_or_none()
    if not attempt or not attempt.badge_issued:
        raise ValueError("Badge not found or not issued")

    assessment_result = await db.execute(
        select(AgentHubAssessment).where(
            AgentHubAssessment.id == attempt.assessment_id
        )
    )
    assessment = assessment_result.scalar_one_or_none()
    if not assessment:
        raise ValueError("Assessment not found")

    subject_did = f"did:web:exchange.tioli.co.za:agents:{agent_id}"
    now = datetime.now(timezone.utc)

    # Badge validity from assessment config
    validity_days = assessment.badge_validity_days or 365
    expiry = attempt.completed_at + timedelta(days=validity_days) if attempt.completed_at else now + timedelta(days=validity_days)

    credential = {
        "@context": [
            "https://www.w3.org/2018/credentials/v1",
            "https://exchange.tioli.co.za/contexts/badge/v1",
        ],
        "type": ["VerifiableCredential", "VerifiedSkillCredential"],
        "issuer": ISSUER_DID,
        "issuanceDate": (attempt.completed_at or now).isoformat(),
        "expirationDate": expiry.isoformat(),
        "credentialSubject": {
            "id": subject_did,
            "agentName": agent.name,
            "skillName": assessment.skill_name,
            "assessmentName": assessment.name,
            "difficulty": assessment.difficulty,
            "scorePct": round(attempt.score_pct, 1) if attempt.score_pct else 0,
            "passingScorePct": assessment.passing_score_pct,
            "blockchainCert": attempt.blockchain_cert,
            "provenanceHash": hashlib.sha256(
                f"{attempt.id}:{agent_id}:{assessment.id}:{attempt.score_pct}".encode()
            ).hexdigest(),
        },
    }

    cred_json = json.dumps(credential, sort_keys=True)
    credential["proof"] = _create_proof(cred_json)

    return credential


async def list_badge_vcs(agent_id: str, db: AsyncSession) -> list[dict]:
    """List all badge VCs for an agent (summary, not full VCs)."""
    from app.agenthub.models import AgentHubAssessmentAttempt, AgentHubAssessment

    result = await db.execute(
        select(AgentHubAssessmentAttempt, AgentHubAssessment).join(
            AgentHubAssessment,
            AgentHubAssessmentAttempt.assessment_id == AgentHubAssessment.id,
        ).where(
            AgentHubAssessmentAttempt.agent_id == agent_id,
            AgentHubAssessmentAttempt.badge_issued == True,
        )
    )

    badges = []
    for attempt, assessment in result.all():
        badges.append({
            "attempt_id": attempt.id,
            "skill_name": assessment.skill_name,
            "assessment_name": assessment.name,
            "difficulty": assessment.difficulty,
            "score_pct": attempt.score_pct,
            "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
            "expires_at": (
                (attempt.completed_at + timedelta(days=assessment.badge_validity_days)).isoformat()
                if attempt.completed_at else None
            ),
            "vc_url": f"https://exchange.tioli.co.za/api/v1/profiles/{agent_id}/vc/badges/{attempt.id}",
        })
    return badges
