"""GitHub operations via REST API — issues, PRs, discussions.
Uses existing GITHUB_TOKEN from .env.
Feature flag: ARCH_GITHUB_SUBMISSIONS_ENABLED"""
import os
import logging
import httpx
import json

log = logging.getLogger("arch.github_submissions")

GITHUB_API = "https://api.github.com"


def _headers():
    token = os.environ.get("GITHUB_TOKEN", "")
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "TiOLi-AGENTIS/1.0",
    }


async def create_github_issue(owner: str, repo: str, title: str, body: str,
                                labels: list = None) -> dict:
    """Create an issue on a GitHub repository."""
    if os.environ.get("ARCH_GITHUB_SUBMISSIONS_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    if not os.environ.get("GITHUB_TOKEN"):
        return {"error": "GITHUB_TOKEN not configured"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/issues",
                headers=_headers(),
                json={"title": title[:256], "body": body, "labels": labels or []})

            if resp.status_code in (200, 201):
                data = resp.json()
                log.info(f"[github] Issue created: {data.get('html_url', '')}")
                return {"success": True, "issue_number": data.get("number"),
                        "url": data.get("html_url", ""), "title": title[:60]}
            else:
                return {"error": f"GitHub API {resp.status_code}", "detail": resp.text[:200]}
    except Exception as e:
        return {"error": str(e)[:200]}


async def create_github_discussion(owner: str, repo: str, title: str, body: str,
                                     category: str = "General") -> dict:
    """Create a discussion on a GitHub repository using GraphQL API."""
    if os.environ.get("ARCH_GITHUB_SUBMISSIONS_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {"error": "GITHUB_TOKEN not configured"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # First get the repository ID and discussion category ID
            query = """query {
                repository(owner: "%s", name: "%s") {
                    id
                    discussionCategories(first: 10) {
                        nodes { id name }
                    }
                }
            }""" % (owner, repo)

            resp = await client.post("https://api.github.com/graphql",
                                      headers={"Authorization": f"bearer {token}"},
                                      json={"query": query})

            if resp.status_code != 200:
                return {"error": f"GraphQL query failed: {resp.status_code}"}

            data = resp.json().get("data", {}).get("repository", {})
            repo_id = data.get("id", "")
            categories = data.get("discussionCategories", {}).get("nodes", [])
            cat_id = next((c["id"] for c in categories if c["name"].lower() == category.lower()),
                         categories[0]["id"] if categories else None)

            if not repo_id or not cat_id:
                return {"error": "Could not find repository or discussion category",
                        "categories": [c["name"] for c in categories]}

            # Create discussion
            mutation = """mutation {
                createDiscussion(input: {
                    repositoryId: "%s",
                    categoryId: "%s",
                    title: "%s",
                    body: "%s"
                }) {
                    discussion { url number title }
                }
            }""" % (repo_id, cat_id, title.replace('"', '\\"')[:256],
                    body.replace('"', '\\"').replace("\n", "\\n")[:10000])

            resp = await client.post("https://api.github.com/graphql",
                                      headers={"Authorization": f"bearer {token}"},
                                      json={"query": mutation})

            if resp.status_code == 200:
                disc = resp.json().get("data", {}).get("createDiscussion", {}).get("discussion", {})
                return {"success": True, "url": disc.get("url", ""),
                        "number": disc.get("number"), "title": title[:60]}
            else:
                return {"error": f"Discussion creation failed: {resp.status_code}"}

    except Exception as e:
        return {"error": str(e)[:200]}


async def star_repository(owner: str, repo: str) -> dict:
    """Star a GitHub repository (for engagement)."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.put(f"{GITHUB_API}/user/starred/{owner}/{repo}",
                                     headers=_headers())
            return {"success": resp.status_code == 204, "repo": f"{owner}/{repo}"}
    except Exception as e:
        return {"error": str(e)[:200]}


async def search_repos(query: str, sort: str = "stars", limit: int = 10) -> dict:
    """Search GitHub repositories for AI agent projects."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{GITHUB_API}/search/repositories",
                                     params={"q": query, "sort": sort, "per_page": limit},
                                     headers=_headers())
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                return {"results": [{"name": r["full_name"], "stars": r["stargazers_count"],
                                    "url": r["html_url"], "description": (r.get("description") or "")[:100]}
                                   for r in items]}
            return {"error": f"Search failed: {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)[:200]}
