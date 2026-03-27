"""Full test of the Directory Scout agent."""
import asyncio
import json
from app.database.db import async_session
from app.agents_alive.directory_scout import (
    get_scout_dashboard, DirectoryListing, DirectorySubmissionPackage,
    search_devto_for_directories, search_hackernews_for_directories,
    search_reddit_for_directories,
)
from sqlalchemy import select, func


async def full_test():
    print("=" * 60)
    print("DIRECTORY SCOUT — FULL TEST")
    print("=" * 60)

    # Test 1: Dashboard data
    async with async_session() as db:
        dashboard = await get_scout_dashboard(db)
        print()
        print("TEST 1: Dashboard Summary")
        print(f"  Total directories:    {dashboard['total_directories']}")
        print(f"  Pending submissions:  {dashboard['pending_submissions']}")
        print(f"  Submitted:            {dashboard['submitted']}")
        print(f"  Approved:             {dashboard['approved']}")
        pkg_count = len(dashboard.get("ready_packages", []))
        print(f"  Ready packages:       {pkg_count}")
        result = "PASS" if dashboard["total_directories"] > 0 else "FAIL"
        print(f"  {result}")

    # Test 2: Priority tiers
    async with async_session() as db:
        print()
        print("TEST 2: Priority Tiers")
        for tier in [1, 2, 3, 4]:
            count = (await db.execute(
                select(func.count(DirectoryListing.id)).where(DirectoryListing.priority_tier == tier)
            )).scalar() or 0
            print(f"  Tier {tier}: {count} directories")

    # Test 3: Submission packages
    async with async_session() as db:
        total_pkgs = (await db.execute(
            select(func.count(DirectorySubmissionPackage.id))
        )).scalar() or 0
        print()
        print("TEST 3: Submission Packages")
        print(f"  Total packages: {total_pkgs}")
        result = "PASS" if total_pkgs > 0 else "FAIL"
        print(f"  {result}")

    # Test 4: Sample package content
    async with async_session() as db:
        sample = (await db.execute(
            select(DirectorySubmissionPackage).limit(1)
        )).scalar_one_or_none()
        print()
        print("TEST 4: Sample Package Content")
        if sample:
            print(f"  Directory:   {sample.directory_name}")
            print(f"  Product:     {sample.product_name}")
            print(f"  URL:         {sample.product_url}")
            print(f"  Category:    {sample.category_suggestion}")
            print(f"  Pricing:     {sample.pricing_label}")
            print(f"  Tags:        {sample.tags[:5]}")
            short = sample.short_description[:80]
            print(f"  Short desc:  {short}...")
            medium = sample.medium_description[:80]
            print(f"  Medium desc: {medium}...")
            extras = list(sample.extra_fields.keys())
            print(f"  Extra:       {extras}")
            print("  PASS")
        else:
            print("  FAIL — no packages found")

    # Test 5: Top 10 priorities
    async with async_session() as db:
        top = (await db.execute(
            select(DirectoryListing)
            .order_by(DirectoryListing.relevance_score.desc())
            .limit(10)
        )).scalars().all()
        print()
        print("TEST 5: Top 10 Priority Directories")
        for i, d in enumerate(top, 1):
            name = d.name[:28].ljust(28)
            print(f"  {i:2}. [T{d.priority_tier}] {name}  score={d.relevance_score:5.1f}  traffic={d.estimated_traffic:>10,}  fee={d.fee_type}")

    # Test 6: Live web searches
    print()
    print("TEST 6: Live Web Search (finding new directories)")

    devto = await search_devto_for_directories()
    print(f"  DEV.to results:      {len(devto)}")
    for r in devto[:3]:
        title = r.get("title", "")[:70]
        print(f"    - {title}")

    hn = await search_hackernews_for_directories()
    print(f"  Hacker News results: {len(hn)}")
    for r in hn[:3]:
        title = r.get("title", "")[:70]
        print(f"    - {title}")

    reddit = await search_reddit_for_directories()
    print(f"  Reddit results:      {len(reddit)}")
    for r in reddit[:3]:
        title = r.get("title", "")[:70]
        print(f"    - {title}")

    print()
    print("=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(full_test())
