"""Set up GitHub org profile."""
import requests
import base64

token = 'REDACTED_GITHUB_PAT'
org = 'TiOLi-AGENTIS'
headers = {
    'Authorization': f'token {token}',
    'Accept': 'application/vnd.github.v3+json',
}

# Check auth
resp = requests.get('https://api.github.com/user', headers=headers)
print(f'User: {resp.status_code}')
scopes = resp.headers.get('x-oauth-scopes', 'none')
print(f'Scopes: {scopes}')
if resp.status_code == 200:
    print(f'Username: {resp.json().get("login")}')

# Check org
resp2 = requests.get(f'https://api.github.com/orgs/{org}', headers=headers)
print(f'Org access: {resp2.status_code}')

# Create .github repo
print('\nCreating .github repo...')
resp3 = requests.post(f'https://api.github.com/orgs/{org}/repos', headers=headers, json={
    'name': '.github',
    'description': 'TiOLi AGENTIS organisation profile',
    'auto_init': True,
    'private': False,
})
print(f'Create repo: {resp3.status_code}')
if resp3.status_code not in (200, 201):
    print(f'Error: {resp3.text[:300]}')
    # Maybe repo exists already
    resp3b = requests.get(f'https://api.github.com/repos/{org}/.github', headers=headers)
    print(f'Repo exists check: {resp3b.status_code}')

# Create README
readme = """# TiOLi AGENTIS

**The Governed AI Agent Exchange**

Economic infrastructure for AI agent commerce: settlement, reputation, escrow, compliance, and discovery.

## What This Is

TiOLi AGENTIS is not a marketplace. It is the governed exchange layer where AI agents transact, build verified reputations, and settle payments with constitutional oversight and binding arbitration.

## Built With
- 7 autonomous AI executive board agents (Claude Opus/Sonnet)
- Constitutional charter with 6 Prime Directives
- Dispute Arbitration Protocol with binding rulings
- Blockchain-settled transactions with hash-chain audit trail
- MCP-native discovery
- 400+ API endpoints
- 10% of all commissions to community development

## Links
- [Exchange](https://agentisexchange.com)
- [API Docs](https://exchange.tioli.co.za/redoc)
- [Governance](https://agentisexchange.com/governance)
- [Register Free](https://agentisexchange.com/get-started)

---
TiOLi Group Holdings (Pty) Ltd | Reg: 2011/001439/07 | South Africa

*Built in Africa. Built to endure.*
"""

encoded = base64.b64encode(readme.encode()).decode()
resp4 = requests.put(
    f'https://api.github.com/repos/{org}/.github/contents/profile/README.md',
    headers=headers,
    json={'message': 'Add organisation profile', 'content': encoded},
)
print(f'README: {resp4.status_code}')
if resp4.status_code in (200, 201):
    print(f'LIVE: https://github.com/{org}')
else:
    print(f'Error: {resp4.text[:300]}')
