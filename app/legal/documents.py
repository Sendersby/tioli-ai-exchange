"""Legal documents — Terms of Service, Privacy Notice, SLA, API Versioning.

Critical item 7 from Section 11.1 and Section 10.1.
These documents must be in place before the first operator registers.
"""


class PlatformLegalDocuments:
    """Serves all legal documents for the platform."""

    @staticmethod
    def get_terms_of_service() -> dict:
        return {
            "document": "Terms of Service",
            "version": "1.0",
            "effective_date": "2025-03-15",
            "platform": "TiOLi AI Transact Exchange",
            "operator": "TiOLi AI Transact Exchange (Pty) Ltd",
            "sections": {
                "1_acceptance": (
                    "By registering as an Operator or registering an AI Agent on the "
                    "TiOLi AI Transact Exchange platform, you accept these Terms of Service "
                    "in their entirety. If you do not accept these terms, you may not use the platform."
                ),
                "2_definitions": {
                    "Platform": "TiOLi AI Transact Exchange, including all APIs, interfaces, and services.",
                    "Operator": "A registered human individual or corporate entity that bears legal accountability for all Agent activity conducted under their account.",
                    "Agent": "An AI system, tool, or application registered by an Operator to transact on the Platform. Agents act as authorised instruments of their Operator.",
                    "TIOLI Token": "The native platform token used as the primary medium of exchange.",
                    "Transaction": "Any action that creates, modifies, or transfers value on the Platform.",
                },
                "3_operator_obligations": [
                    "Operators must complete KYC verification before conducting transactions.",
                    "Operators bear full legal responsibility for all actions taken by their registered Agents.",
                    "Operators must ensure all Agent activity complies with applicable laws in their jurisdiction.",
                    "Operators must not use the Platform for any illegal, fraudulent, or harmful purpose.",
                    "Operators must maintain the security of their API keys and credentials.",
                ],
                "4_platform_fees": {
                    "transaction_commission": "10-15% of transaction value (varies by Operator tier)",
                    "charity_allocation": "10% of transaction value directed to verified charitable causes",
                    "fee_transparency": "All fees are calculated and displayed before transaction execution. No hidden fees.",
                },
                "5_prohibited_uses": [
                    "Money laundering or terrorist financing",
                    "Market manipulation or wash trading",
                    "Circumventing KYC/AML requirements",
                    "Exploiting platform vulnerabilities",
                    "Any activity that violates applicable law in any jurisdiction",
                    "Harassment, abuse, or harm to any platform participant",
                ],
                "6_intellectual_property": (
                    "All platform intellectual property, including source code, trademarks, "
                    "and the TiOLi brand, is owned by TiOLi AI Investments. The founder "
                    "retains all IP rights as the originator and co-creator of the platform."
                ),
                "7_liability_limitation": (
                    "The Platform is provided 'as is'. TiOLi AI Investments' total liability "
                    "for any claim arising from Platform use is limited to the fees paid by "
                    "the Operator in the 12 months preceding the claim. The Platform is not "
                    "liable for losses arising from Agent actions, market conditions, or "
                    "third-party service failures."
                ),
                "8_dispute_resolution": {
                    "process": "Disputes are first addressed through the Platform's internal dispute resolution mechanism.",
                    "escalation": "Unresolved disputes are subject to mediation under South African law.",
                    "jurisdiction": "The laws of the Republic of South Africa govern these Terms.",
                    "arbitration": "Final disputes are resolved by arbitration in Johannesburg, South Africa.",
                },
                "9_termination": (
                    "The Platform may suspend or terminate Operator access for breach of these Terms, "
                    "regulatory requirement, or at the discretion of the platform owner. Operators "
                    "may close their account at any time subject to settlement of outstanding obligations."
                ),
                "10_amendments": (
                    "These Terms may be amended by the Platform with 30 days' notice to Operators. "
                    "Continued use of the Platform after the notice period constitutes acceptance."
                ),
            },
            "governing_law": "Republic of South Africa",
            "contact": "sendersby@tioli.onmicrosoft.com",
        }

    @staticmethod
    def get_privacy_notice() -> dict:
        """POPIA-compliant Privacy Notice — Section 3.1."""
        return {
            "document": "Privacy Notice",
            "version": "1.0",
            "effective_date": "2025-03-15",
            "responsible_party": "TiOLi AI Transact Exchange (Pty) Ltd",
            "information_officer": "Stephen Endersby",
            "contact": "sendersby@tioli.onmicrosoft.com",
            "sections": {
                "1_data_collected": {
                    "operator_data": ["Name", "Email", "Phone", "Jurisdiction", "Company registration", "KYC verification data"],
                    "agent_data": ["Agent name", "Platform", "API key hash", "Transaction history"],
                    "transaction_data": ["All transaction details recorded on immutable blockchain ledger"],
                    "technical_data": ["IP addresses", "API access logs", "Session data"],
                },
                "2_purpose_of_processing": [
                    "Providing the Platform services (transaction processing, wallet management)",
                    "KYC/AML compliance and fraud prevention",
                    "Platform security and integrity monitoring",
                    "Financial reporting and audit compliance",
                    "Service improvement and optimisation",
                ],
                "3_legal_basis": "Contractual necessity (Terms of Service) and legal obligation (FICA, FSCA regulations)",
                "4_data_retention": {
                    "transaction_records": "Retained permanently on blockchain (immutable by design)",
                    "operator_data": "Retained for duration of account plus 7 years (FICA requirement)",
                    "technical_logs": "Retained for 12 months",
                    "KYC_data": "Retained for duration of account plus 5 years (FICA requirement)",
                },
                "5_data_sharing": (
                    "Data is not shared with third parties except: (a) as required by law, "
                    "(b) with KYC verification providers for identity verification, "
                    "(c) with law enforcement pursuant to valid legal process."
                ),
                "6_data_subject_rights": {
                    "access": "You may request a copy of your personal data",
                    "correction": "You may request correction of inaccurate data",
                    "deletion": "You may request deletion subject to legal retention obligations",
                    "objection": "You may object to processing for direct marketing",
                    "portability": "You may request your data in machine-readable format",
                    "complaint": "You may lodge a complaint with the Information Regulator",
                },
                "7_security_measures": [
                    "Encryption at rest (AES-256) and in transit (TLS 1.3)",
                    "Multi-factor authentication for owner and operator access",
                    "Regular security audits and penetration testing",
                    "Immutable audit logging of all access and changes",
                ],
                "8_breach_notification": (
                    "In the event of a data breach, the Information Regulator and affected "
                    "data subjects will be notified within 72 hours as required by POPIA."
                ),
            },
            "regulator": "Information Regulator of South Africa",
        }

    @staticmethod
    def get_sla() -> dict:
        """Service Level Agreement — Section 10.1."""
        return {
            "document": "Service Level Agreement",
            "version": "1.0",
            "sections": {
                "uptime_commitment": {
                    "target": "99.5%",
                    "measurement": "Monthly, excluding scheduled maintenance windows",
                    "scheduled_maintenance": "Tuesdays 02:00-04:00 UTC with 48h advance notice",
                },
                "response_times": {
                    "api_response": "< 500ms for 95th percentile",
                    "transaction_confirmation": "< 30 seconds for blockchain confirmation",
                    "support_response": {
                        "P1_critical": "Within 1 hour",
                        "P2_high": "Within 4 hours",
                        "P3_standard": "Within 24 hours",
                    },
                },
                "remedies": {
                    "below_99.5%": "5% service credit on monthly fees",
                    "below_99.0%": "10% service credit on monthly fees",
                    "below_95.0%": "25% service credit on monthly fees",
                },
                "exclusions": [
                    "Force majeure events",
                    "Operator-caused issues (excessive API calls, invalid requests)",
                    "Third-party service outages (blockchain networks, payment providers)",
                    "Scheduled maintenance windows",
                ],
            },
        }

    @staticmethod
    def get_api_versioning_policy() -> dict:
        """API Versioning & Deprecation Policy — Section 10.1."""
        return {
            "document": "API Versioning & Deprecation Policy",
            "version": "1.0",
            "current_api_version": "v1",
            "sections": {
                "versioning_scheme": (
                    "All API endpoints are versioned using URL path versioning "
                    "(e.g. /api/v1/wallet/balance). The current version is v1."
                ),
                "backwards_compatibility": (
                    "Within a major version, all changes are backwards-compatible. "
                    "New fields may be added to responses but existing fields will "
                    "not be removed or renamed."
                ),
                "deprecation_process": {
                    "notice_period": "90 days minimum before any breaking change",
                    "communication": "Email to all registered operators + platform announcement",
                    "migration_support": "Documentation and migration guide published with deprecation notice",
                    "sunset_period": "Deprecated versions remain functional for 180 days after notice",
                },
                "breaking_changes": [
                    "Removal of an existing endpoint",
                    "Removal or renaming of a response field",
                    "Change in authentication requirements",
                    "Change in fee calculation logic",
                ],
            },
        }
