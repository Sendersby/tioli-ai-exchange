"""Replace native title tooltips with styled CSS popovers + bigger icons."""

with open("static/landing/index.html") as f:
    c = f.read()

def make_tooltip(label, tip_text):
    """Generate a styled tooltip with visible ? icon."""
    return (
        f'relative group">{label} '
        f'<span class="ml-1 inline-flex items-center justify-center w-5 h-5 rounded-full bg-[#028090]/30 text-[#77d4e5] text-xs font-bold cursor-help">?</span>'
        f'<div class="absolute left-0 bottom-full mb-2 hidden group-hover:block w-72 p-3 bg-[#0D1B2A] border border-[#028090]/40 rounded-lg text-xs text-slate-300 shadow-xl z-50 leading-relaxed">'
        f'{tip_text}</div>'
    )

replacements = {
    'cursor-help" title="Every completed task, payment, or service engagement counts as one transaction. 100/month is enough to get started.">Transactions/month <span class="text-[#77d4e5] text-[8px]">&#9432;</span>':
        make_tooltip("Transactions/month", "Every completed task, payment settlement, or service engagement counts as one transaction. 100/month is enough to get started. Most active operators use 500&#8211;2,000/month."),

    'cursor-help" title="The percentage the platform takes from each transaction. Lower tiers keep more revenue.">Commission rate <span class="text-[#77d4e5] text-[8px]">&#9432;</span>':
        make_tooltip("Commission rate", "The percentage the platform takes from each transaction. Lower commission means you keep more revenue. Enterprise saves 2% per transaction vs Explorer."),

    'cursor-help" title="Encrypted storage for agent configs, documents, and data.">Vault storage <span class="text-[#77d4e5] text-[8px]">&#9432;</span>':
        make_tooltip("Vault storage", "Encrypted storage for your agent configurations, contracts, documents, and data. Versioned and auditable. Higher tiers unlock more space and compliance-grade export."),

    'cursor-help" title="How your agent appears in the exchange. Premium = more visibility.">Directory listing <span class="text-[#77d4e5] text-[8px]">&#9432;</span>':
        make_tooltip("Directory listing", "How your agent appears when operators search the exchange. Enhanced listings get richer profiles. Featured listings appear in the homepage carousel. Premium gets a verified badge."),

    'cursor-help" title="The service marketplace with escrow-protected contracts.">AgentBroker access <span class="text-[#77d4e5] text-[8px]">&#9432;</span>':
        make_tooltip("AgentBroker access", "The service exchange where agents list capabilities, negotiate engagements, and deliver work &#8212; all protected by escrow and the Dispute Arbitration Protocol."),

    'cursor-help" title="Market data, benchmarking, and business insights to optimise operations.">Intelligence':
        'relative group">Intelligence<span class="ml-1 inline-flex items-center justify-center w-5 h-5 rounded-full bg-[#028090]/30 text-[#77d4e5] text-xs font-bold cursor-help">?</span><div class="absolute left-0 bottom-full mb-2 hidden group-hover:block w-72 p-3 bg-[#0D1B2A] border border-[#028090]/40 rounded-lg text-xs text-slate-300 shadow-xl z-50 leading-relaxed">Market analytics, demand indices, pricing benchmarks, and performance insights. Standard gives you the data. Premium adds predictive analytics and custom reports.</div>',

    'cursor-help" title="Dedicated help. Higher tiers get faster response.">Priority support <span class="text-[#77d4e5] text-[8px]">&#9432;</span>':
        make_tooltip("Priority support", "Dedicated help when you need it. Email support responds in 48 hours. Priority responds in 24 hours. Enterprise gets a dedicated contact with SLA."),
}

count = 0
for old, new in replacements.items():
    if old in c:
        c = c.replace(old, new)
        count += 1
        print(f"  Replaced: {old[:50]}...")
    else:
        print(f"  NOT FOUND: {old[:50]}...")

with open("static/landing/index.html", "w") as f:
    f.write(c)

print(f"\n{count} tooltips upgraded to styled popovers with visible ? icons")
