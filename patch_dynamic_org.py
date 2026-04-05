"""Patch views.py — make organogram fully dynamic from database."""
import json

with open("app/boardroom/views.py") as f:
    content = f.read()

# Find the org_design function and replace the department building logic
# We need to replace everything between the AGENT_ASSIGNMENTS and system_accounts

# Find the start of assignments
marker1 = "# 5-layer architecture mapping"
marker2 = '    ctx["system_accounts"]'

if marker1 not in content:
    marker1 = "# FULLY DYNAMIC"

idx1 = content.index(marker1)
idx2 = content.index(marker2)

# Get everything before and after
before = content[:idx1]
after = content[idx2:]

# New dynamic code
new_code = '''    # FULLY DYNAMIC — pull ALL agents from database and subordinate registry
    sub_events = await db.execute(text(
        "SELECT DISTINCT ON (event_data->>'subordinate_name') "
        "event_data FROM arch_platform_events "
        "WHERE event_type = 'agent.subordinate_created' "
        "ORDER BY event_data->>'subordinate_name', created_at DESC"
    ))

    subs_by_arch = {}
    for row in sub_events.fetchall():
        data = json.loads(row.event_data) if isinstance(row.event_data, str) else row.event_data
        arch = data.get("managing_arch_agent", "architect")
        if arch not in subs_by_arch:
            subs_by_arch[arch] = []

        agent_check = await db.execute(text(
            "SELECT is_active FROM agents WHERE name = :n LIMIT 1"
        ), {"n": data.get("subordinate_name", "")})
        agent_row = agent_check.fetchone()
        is_active = agent_row.is_active if agent_row else False

        subs_by_arch[arch].append({
            "name": data.get("subordinate_name", ""),
            "platform": data.get("platform", ""),
            "description": data.get("description", "")[:100],
            "layer": data.get("layer", 2),
            "layer_name": data.get("layer_name", ""),
            "category": data.get("category", "operational"),
            "shared": False,
            "active": is_active,
            "status": "active" if is_active else "inactive",
        })

    TITLES = {
        "sentinel": ("COO & CISO", "Security & Operations"),
        "sovereign": ("CEO & Board Chair", "Governance & Community"),
        "treasurer": ("CFO & CIO", "Finance & Analytics"),
        "auditor": ("Chief Legal & Compliance", "Legal & Regulatory"),
        "arbiter": ("Chief Product & Justice", "Quality & Dispute Resolution"),
        "architect": ("CTO & Innovation", "Technology & Engineering"),
        "ambassador": ("CMO & Growth", "Growth & Content"),
    }

    departments = []
    for agent_info in ctx["agents"]:
        agent_name = agent_info["name"]
        title_info = TITLES.get(agent_name, ("", ""))
        subs = subs_by_arch.get(agent_name, [])
        departments.append({
            "name": agent_name,
            "display": agent_info["display"],
            "title": title_info[0],
            "layer_label": title_info[1],
            "colour": agent_info["colour"],
            "abbrev": agent_info["abbrev"],
            "subordinates": sorted(subs, key=lambda s: (s["layer"], s["name"])),
            "sub_count": len(subs),
            "active_count": sum(1 for s in subs if s["active"]),
        })

    ctx["departments"] = departments
    '''

content = before + new_code + after

with open("app/boardroom/views.py", "w") as f:
    f.write(content)
print("Views patched — fully dynamic organogram")
