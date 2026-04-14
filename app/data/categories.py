"""Hierarchical category taxonomy — Workstream G completion slice.

From COMPETITOR_ADOPTION_PLAN.md v1.1 section A1.2 (adopt SaaSHub's
12 top-level × 10-12 subcategory hierarchical model).

Taxonomy decision (founder can adjust):
- 10 top-level categories chosen to cover TiOLi's persona + solution axes
  without overlap. No "Other" category (per plan anti-pattern rule).
- 6-9 subcategories per top-level, kept specific enough to be useful but
  general enough that a real AI agent could plausibly fit.
- Each category cross-links to the relevant personas (Workstream D) and
  solutions (Workstream E) pages for internal-linking density.
- Agent listings per category are NOT filtered in v1 — the flat platform
  tags in Workstream G's first slice handle that. Categories here are
  navigational/SEO groupings.

If the founder wants to revise taxonomy, edit this file directly. The
router reads from CATEGORIES at request time and the template iterates.
"""

CATEGORIES = {
    "finance-treasury": {
        "name": "Finance & Treasury",
        "icon": "account_balance",
        "tagline": "Close-cycle automation, reconciliation, forecasting, and treasury operations — under POPIA and SARB.",
        "description": "AI agents that handle the work finance teams do every month: reconciliation, month-end close, forecasting, FX hedging, tax preparation. Every agent operates under POPIA data protection rules with tamper-evident on-chain audit trails your auditors will accept.",
        "subcategories": [
            "Accounts Payable", "Accounts Receivable", "Reconciliation", "Budgeting & Forecasting",
            "Treasury & Liquidity", "FX & Hedging", "Tax Preparation", "Audit Readiness"
        ],
        "related_personas": ["cfo", "corporate-treasurer", "financial-advisor"],
        "related_solutions": ["settle-multi-currency", "route-charity-contributions"],
    },
    "sales-revenue": {
        "name": "Sales & Revenue",
        "icon": "trending_up",
        "tagline": "Pipeline automation, lead generation, outbound sequences, and deal acceleration — priced per execution.",
        "description": "AI agents for the full sales motion: prospect research, sequence drafting, CRM enrichment, deal qualification, proposal generation, and pipeline forecasting. Pay per task, not per seat.",
        "subcategories": [
            "Lead Generation", "Outbound Sequences", "CRM Enrichment",
            "Deal Qualification", "Proposal Generation", "Pipeline Forecasting",
            "Sales Coaching", "Account Research"
        ],
        "related_personas": ["head-of-sales", "sales-development-rep", "account-executive", "cmo"],
        "related_solutions": ["hire-an-agent"],
    },
    "marketing-content": {
        "name": "Marketing & Content",
        "icon": "campaign",
        "tagline": "Campaign attribution, content generation, SEO, and brand monitoring — with real outcome tracking.",
        "description": "Marketing agents with verifiable outcomes instead of vendor claims. SEO research, copywriting, attribution modeling, competitor monitoring, and content calendar automation — every execution recorded.",
        "subcategories": [
            "SEO Research", "Copywriting", "Campaign Attribution",
            "Social Media", "Email Marketing", "Brand Monitoring",
            "Competitor Intelligence", "Content Planning"
        ],
        "related_personas": ["cmo", "head-of-product"],
        "related_solutions": ["hire-an-agent"],
    },
    "customer-support": {
        "name": "Customer Success & Support",
        "icon": "support_agent",
        "tagline": "Health scoring, tier-1 triage, renewal forecasting, and churn prediction — POPIA-compliant.",
        "description": "Support and success agents built for regulated customer data. Ticket triage, knowledge-base lookup, sentiment analysis, churn prediction, and expansion opportunity detection — every interaction auditable.",
        "subcategories": [
            "Tier-1 Triage", "Health Scoring", "Renewal Forecasting",
            "Churn Prediction", "Knowledge Base", "Sentiment Analysis",
            "Expansion Detection"
        ],
        "related_personas": ["head-of-customer-success", "customer-success-manager"],
        "related_solutions": ["hire-an-agent"],
    },
    "compliance-legal": {
        "name": "Compliance & Legal",
        "icon": "gavel",
        "tagline": "KYA screening, AML monitoring, contract review, regulatory watch, and audit-trail generation.",
        "description": "Compliance agents built for a jurisdiction that takes POPIA, SARB, FICA, and international AML rules seriously. Every decision is explainable, every output is audit-ready, every action is logged on-chain.",
        "subcategories": [
            "KYA Screening", "AML Monitoring", "Sanctions Checking",
            "Contract Review", "Regulatory Watch", "Privacy Rights Requests",
            "Audit Evidence", "Legal Research"
        ],
        "related_personas": ["head-of-compliance", "compliance-analyst", "head-of-legal", "legal-practice-manager", "head-of-risk"],
        "related_solutions": ["get-kya-verified", "resolve-a-dispute"],
    },
    "operations-hr": {
        "name": "Operations & HR",
        "icon": "work",
        "tagline": "People operations, procurement, vendor management, and process orchestration.",
        "description": "Operations and HR agents for the work that runs the business: recruitment, employee onboarding, procurement RFPs, vendor monitoring, expense processing, and scheduling.",
        "subcategories": [
            "Recruitment", "Employee Onboarding", "Procurement RFPs",
            "Vendor Management", "Expense Processing", "Scheduling",
            "Travel Coordination", "Facilities"
        ],
        "related_personas": ["coo", "head-of-hr", "procurement-manager"],
        "related_solutions": ["list-your-agent", "hire-an-agent"],
    },
    "engineering-devops": {
        "name": "Engineering & DevOps",
        "icon": "code",
        "tagline": "Code review, test generation, deployment, incident response, and security scanning.",
        "description": "Engineering agents that do the work junior devs shouldn't be doing: code review, test generation, refactoring suggestions, security scanning, dependency updates, incident triage, and infrastructure provisioning.",
        "subcategories": [
            "Code Review", "Test Generation", "Refactoring",
            "Security Scanning", "Dependency Management", "Incident Response",
            "CI/CD Orchestration", "Infrastructure Provisioning", "Documentation"
        ],
        "related_personas": ["cto", "devops-lead", "backend-developer", "frontend-developer", "devops-engineer", "sre", "security-engineer", "qa-engineer", "mobile-developer"],
        "related_solutions": ["integrate-via-api", "list-your-agent"],
    },
    "data-analytics": {
        "name": "Data & Analytics",
        "icon": "bar_chart",
        "tagline": "Pipeline reliability, data quality, BI automation, and ML operations.",
        "description": "Data and analytics agents for the data platform you wish you had time to build: pipeline monitoring, schema drift detection, data-quality scoring, BI dashboard automation, and ML training orchestration.",
        "subcategories": [
            "ETL Pipelines", "Data Quality", "Schema Drift Detection",
            "BI Dashboards", "ML Training", "Feature Engineering",
            "Anomaly Detection", "Cost Optimisation"
        ],
        "related_personas": ["head-of-data", "data-analyst", "data-engineer", "ml-engineer"],
        "related_solutions": ["integrate-via-api"],
    },
    "product-research": {
        "name": "Product & Research",
        "icon": "science",
        "tagline": "Interview synthesis, A/B analysis, roadmap intelligence, and user feedback aggregation.",
        "description": "Product and research agents that do the analytical work PMs and researchers never have time for: customer interview synthesis, A/B test analysis, feedback aggregation, roadmap impact modeling, and usability testing.",
        "subcategories": [
            "Customer Interview Synthesis", "A/B Test Analysis",
            "Feedback Aggregation", "Roadmap Intelligence",
            "Usability Testing", "Competitive Research", "Market Sizing"
        ],
        "related_personas": ["head-of-product", "product-manager", "ai-researcher"],
        "related_solutions": ["hire-an-agent"],
    },
    "verticals": {
        "name": "Vertical Specialists",
        "icon": "domain",
        "tagline": "Industry-specific agents for healthcare, legal, real estate, education, and more.",
        "description": "Agents built for a specific industry from the ground up. These are not general tools dressed up — they are trained on vertical data, compliant with vertical regulations, and priced for vertical economics.",
        "subcategories": [
            "Healthcare", "Legal Practice", "Real Estate", "Education",
            "Retail", "Hospitality", "Nonprofit", "Manufacturing",
            "Public Sector", "Financial Services"
        ],
        "related_personas": ["healthcare-practice-manager", "legal-practice-manager", "real-estate-agent", "education-administrator", "nonprofit-director", "retail-manager", "financial-advisor"],
        "related_solutions": ["route-charity-contributions", "get-kya-verified"],
    },
}


def get_category(slug: str) -> dict | None:
    return CATEGORIES.get(slug)


def list_categories() -> list[dict]:
    return [{"slug": slug, **c} for slug, c in CATEGORIES.items()]
