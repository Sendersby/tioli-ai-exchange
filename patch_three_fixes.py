"""Three fixes: terminated toggle, deeper live feed, clickable abbreviations."""

# Fix 1 + 2: Org design template
with open("app/templates/boardroom/org_design.html") as f:
    c = f.read()

# Fix terminated toggle — ensure clicking toggles visibility properly
c = c.replace(
    "btn.style.opacity = '0.4';\n  }\n  applyAllFilters();\n}",
    "btn.style.opacity = '0.4';\n  }\n  applyAllFilters();\n}\n"
)

# Fix applyAllFilters to properly show/hide terminated + inactive
old_status = """    const status = (card.dataset.status || 'active').toLowerCase();
    if (status === 'active' && !activeFilters.active) card.style.display = 'none';
    else if (status === 'paused' && !activeFilters.paused) card.style.display = 'none';
    else if (status === 'terminated' && !activeFilters.terminated) card.style.display = 'none';"""

new_status = """    const status = (card.dataset.status || 'active').toLowerCase();
    let visible = true;
    if (status === 'active' && !activeFilters.active) visible = false;
    if (status === 'paused' && !activeFilters.paused) visible = false;
    if ((status === 'terminated' || status === 'inactive') && !activeFilters.terminated) visible = false;
    card.style.display = visible ? '' : 'none';"""

c = c.replace(old_status, new_status)

with open("app/templates/boardroom/org_design.html", "w") as f:
    f.write(c)
print("Fix 1: Terminated toggle fixed")

# Fix 3: Deeper live activity feed on Board Home
with open("app/templates/boardroom/home.html") as f:
    h = f.read()

# Make the live feed taller
h = h.replace('max-h-64 overflow-y-auto', 'max-h-[500px] overflow-y-auto')

# Make agent abbreviations in the feed clickable
old_abbrev = '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold" style="background-color: {{ f.colour }}20; color: {{ f.colour }}">{{ f.abbrev }}</span>'
new_abbrev = '<a href="/boardroom/agents/{{ f.agent }}" class="px-1.5 py-0.5 rounded text-[10px] font-bold hover:opacity-80 transition-opacity" style="background-color: {{ f.colour }}20; color: {{ f.colour }}">{{ f.abbrev }}</a>'
h = h.replace(old_abbrev, new_abbrev)

# Also increase the feed limit in views.py from 20 to 50
with open("app/boardroom/views.py") as f:
    v = f.read()
v = v.replace(
    "FROM arch_event_actions ORDER BY created_at DESC LIMIT 20",
    "FROM arch_event_actions ORDER BY created_at DESC LIMIT 50"
)
with open("app/boardroom/views.py", "w") as f:
    f.write(v)

with open("app/templates/boardroom/home.html", "w") as f:
    f.write(h)
print("Fix 2: Live feed deeper (500px, 50 entries)")
print("Fix 3: Agent abbreviations clickable in feed")
