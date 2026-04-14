"""Curated list of external AI agent / AI tool directories — Workstream R.

From COMPETITOR_ADOPTION_PLAN.md v1.1. This is the seed data for the
cross-directory submission service: we maintain a vetted list of external
directories, their submission URLs, and notes about their submission
format (manual form / email / API / manual outreach).

Adding a new directory: append to EXTERNAL_DIRECTORIES. The router reads
at request time so no template changes are needed.

Important: the URLs below are the *submission* URLs, not the directory
homepages. These need occasional manual re-verification — we add a
scheduler job in a later slice to check each URL is still reachable.
"""

EXTERNAL_DIRECTORIES = [
    {"slug": "theresanaiforthat", "name": "There's An AI For That", "homepage": "https://theresanaiforthat.com", "submission_url": "https://theresanaiforthat.com/submit/", "format": "form", "traffic_band": "high", "notes": "Largest consumer-facing AI tool directory. Form submission, free. Review queue typically 1-2 weeks."},
    {"slug": "aiagentstore", "name": "aiagentstore.ai", "homepage": "https://aiagentstore.ai", "submission_url": "https://aiagentstore.ai/new-agent", "format": "form", "traffic_band": "medium", "notes": "Dedicated AI agent directory with 5,000+ programmatic pages. One-field-first submission, 7-step wizard follows."},
    {"slug": "futurepedia", "name": "Futurepedia", "homepage": "https://www.futurepedia.io", "submission_url": "https://www.futurepedia.io/submit-tool", "format": "form", "traffic_band": "high", "notes": "Large consumer AI tool directory. Free basic submission, paid featured placement."},
    {"slug": "futuretools", "name": "Future Tools", "homepage": "https://www.futuretools.io", "submission_url": "https://www.futuretools.io/submit-a-tool", "format": "form", "traffic_band": "high", "notes": "Curated list. Matt Wolfe audience. Moderate review gate."},
    {"slug": "toolify", "name": "Toolify.ai", "homepage": "https://www.toolify.ai", "submission_url": "https://www.toolify.ai/submit", "format": "form", "traffic_band": "medium", "notes": "Large catalogue, SEO-heavy. Free submission."},
    {"slug": "topai-tools", "name": "Top AI Tools", "homepage": "https://topai.tools", "submission_url": "https://topai.tools/submit", "format": "form", "traffic_band": "medium", "notes": "Category-organised directory, daily updates."},
    {"slug": "easywithai", "name": "Easy With AI", "homepage": "https://easywithai.com", "submission_url": "https://easywithai.com/submit-ai-tool/", "format": "form", "traffic_band": "medium", "notes": "Consumer-friendly AI tool listings."},
    {"slug": "aitooltracker", "name": "AI Tool Tracker", "homepage": "https://aitooltracker.io", "submission_url": "https://aitooltracker.io/submit", "format": "form", "traffic_band": "low", "notes": "Newer directory with weekly digests."},
    {"slug": "aitoolhunt", "name": "AI Tool Hunt", "homepage": "https://www.aitoolhunt.com", "submission_url": "https://www.aitoolhunt.com/submit-tool", "format": "form", "traffic_band": "medium", "notes": "Categorised AI tool directory with user ratings."},
    {"slug": "supertools", "name": "Supertools (The Rundown)", "homepage": "https://supertools.therundown.ai", "submission_url": "https://supertools.therundown.ai/submit", "format": "form", "traffic_band": "high", "notes": "Supertools by The Rundown newsletter. High-traffic editorial filter."},
    {"slug": "aiagentindex-mit", "name": "MIT AI Agent Index", "homepage": "https://aiagentindex.mit.edu", "submission_url": "mailto:aiagentindex@mit.edu", "format": "email", "traffic_band": "medium", "notes": "Academic index by MIT Media Lab. Email submission with academic tone. Credibility signal."},
    {"slug": "agent-ai", "name": "Agent.ai", "homepage": "https://agent.ai", "submission_url": "https://agent.ai/submit", "format": "form", "traffic_band": "medium", "notes": "HubSpot-backed agent directory. Free submission."},
    {"slug": "allthingsai", "name": "All Things AI", "homepage": "https://allthingsai.com", "submission_url": "https://allthingsai.com/submit", "format": "form", "traffic_band": "low", "notes": "Older directory, still accepting submissions."},
    {"slug": "productivly", "name": "Productivly", "homepage": "https://productivly.com", "submission_url": "https://productivly.com/submit", "format": "form", "traffic_band": "low", "notes": "Productivity-focused AI tool catalogue."},
    {"slug": "aigents-directory", "name": "AIgents Directory", "homepage": "https://aigents.directory", "submission_url": "https://aigents.directory/submit", "format": "form", "traffic_band": "low", "notes": "Agent-specific directory. Free basic listing."},
    {"slug": "aixploria", "name": "Aixploria", "homepage": "https://www.aixploria.com", "submission_url": "https://www.aixploria.com/en/submit-your-ai/", "format": "form", "traffic_band": "medium", "notes": "French-language friendly, European audience."},
    {"slug": "find-ai", "name": "Find AI", "homepage": "https://find-ai.com", "submission_url": "https://find-ai.com/submit", "format": "form", "traffic_band": "low", "notes": "Smaller but clean category filtering."},
    {"slug": "product-hunt", "name": "Product Hunt", "homepage": "https://www.producthunt.com", "submission_url": "https://www.producthunt.com/posts/new", "format": "manual", "traffic_band": "very-high", "notes": "Not AI-specific but high traffic. Requires hunter + maker setup. Launch-day only."},
    {"slug": "hackernews-show", "name": "Hacker News — Show HN", "homepage": "https://news.ycombinator.com", "submission_url": "https://news.ycombinator.com/submit", "format": "manual", "traffic_band": "very-high", "notes": "Show HN for launches. No guarantee of front-page. Technical audience."},
    {"slug": "betalist", "name": "BetaList", "homepage": "https://betalist.com", "submission_url": "https://betalist.com/submit", "format": "form", "traffic_band": "medium", "notes": "Startup discovery before launch. Pre-launch listings welcome."},
    {"slug": "saashub", "name": "SaaSHub", "homepage": "https://www.saashub.com", "submission_url": "https://www.saashub.com/submit-software", "format": "form", "traffic_band": "high", "notes": "218K+ products, has user ratings. Free submission."},
    {"slug": "alternativeto", "name": "AlternativeTo", "homepage": "https://alternativeto.net", "submission_url": "https://alternativeto.net/add-app/", "format": "form", "traffic_band": "very-high", "notes": "Largest alternatives directory. Good for SEO backlinks."},
    {"slug": "g2", "name": "G2", "homepage": "https://www.g2.com", "submission_url": "https://my.g2.com/dashboard", "format": "manual", "traffic_band": "very-high", "notes": "Enterprise software reviews. Requires vendor account. Gate: has real customers."},
    {"slug": "capterra", "name": "Capterra", "homepage": "https://www.capterra.com", "submission_url": "https://www.capterra.com/vendors/sign-up", "format": "manual", "traffic_band": "very-high", "notes": "Gartner-owned. Enterprise discovery. Vendor account required."},
    {"slug": "marketplace-a2a", "name": "A2A Marketplace Directory", "homepage": "https://a2a.dev", "submission_url": "https://a2a.dev/submit", "format": "form", "traffic_band": "medium", "notes": "A2A protocol directory for agent-to-agent interop. TiOLi is especially well-placed here given did:web integration."},
]


def list_directories():
    return EXTERNAL_DIRECTORIES


def get_directory(slug: str):
    for d in EXTERNAL_DIRECTORIES:
        if d["slug"] == slug:
            return d
    return None


def count_by_band():
    counts = {}
    for d in EXTERNAL_DIRECTORIES:
        band = d.get("traffic_band", "unknown")
        counts[band] = counts.get(band, 0) + 1
    return counts
