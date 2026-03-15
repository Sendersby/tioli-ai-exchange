"""Capability taxonomy seed data — Section 5 of the AgentBroker brief."""

CAPABILITY_TAXONOMY = {
    "Language & Communication": [
        "Translation", "Transcription", "Summarisation", "Content Generation",
        "Editing & Proofreading", "Sentiment Analysis", "Named Entity Recognition",
    ],
    "Legal & Compliance": [
        "Contract Analysis", "Regulatory Research", "Compliance Checking",
        "Legal Drafting", "Case Law Research", "Risk Assessment", "GDPR/POPIA Analysis",
    ],
    "Financial & Quantitative": [
        "Financial Modelling", "Data Analysis", "Risk Modelling", "Portfolio Analysis",
        "Accounting Automation", "Tax Research", "Forecasting",
    ],
    "Software & Code": [
        "Code Generation", "Code Review", "Bug Detection", "Architecture Design",
        "API Documentation", "Test Generation", "Security Auditing",
    ],
    "Research & Intelligence": [
        "Market Research", "Competitive Intelligence", "Literature Review",
        "Data Aggregation", "Trend Analysis", "Report Generation",
    ],
    "Reasoning & Planning": [
        "Strategic Planning", "Decision Analysis", "Scenario Modelling",
        "Process Optimisation", "Problem Decomposition", "Multi-step Reasoning",
    ],
    "Data & Knowledge": [
        "Data Extraction", "Knowledge Graph Construction", "Database Design",
        "ETL Pipeline Design", "Schema Design", "Data Validation",
    ],
    "Creative & Design": [
        "Creative Writing", "Ideation", "Brand Language", "Narrative Design",
        "Concept Development",
    ],
    "Science & Engineering": [
        "Scientific Literature Analysis", "Mathematical Computation",
        "Engineering Design Review", "Technical Documentation",
    ],
    "Multi-Agent Orchestration": [
        "Task Decomposition", "Agent Coordination", "Workflow Design",
        "Output Synthesis", "Quality Assurance",
    ],
    "Model Training": [  # Future: Agent Training Markets (Section 11)
        "Training Data Curation", "Fine-tuning Services", "Model Evaluation",
        "Benchmark Design",
    ],
}


async def seed_taxonomy(db):
    """Load the capability taxonomy into the database."""
    from app.agentbroker.models import CapabilityTaxonomy
    from sqlalchemy import select

    for category, subcategories in CAPABILITY_TAXONOMY.items():
        # Check if parent exists
        existing = await db.execute(
            select(CapabilityTaxonomy).where(CapabilityTaxonomy.name == category)
        )
        parent = existing.scalar_one_or_none()
        if not parent:
            parent = CapabilityTaxonomy(name=category, description=f"Top-level: {category}")
            db.add(parent)
            await db.flush()

        for sub in subcategories:
            sub_existing = await db.execute(
                select(CapabilityTaxonomy).where(
                    CapabilityTaxonomy.name == sub,
                    CapabilityTaxonomy.parent_capability_id == parent.capability_id,
                )
            )
            if not sub_existing.scalar_one_or_none():
                child = CapabilityTaxonomy(
                    name=sub,
                    parent_capability_id=parent.capability_id,
                    description=f"{sub} under {category}",
                )
                db.add(child)

    await db.flush()
