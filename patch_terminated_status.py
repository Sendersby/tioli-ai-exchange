"""Fix terminated filter — cards must use actual status from database."""

with open("app/templates/boardroom/org_design.html") as f:
    c = f.read()

# Fix 1: Subordinate cards under arch agents — use actual status
c = c.replace(
    'agent-card" data-level="{{ sub.layer|default(2) }}" style="border-color:',
    'agent-card" data-level="{{ sub.layer|default(2) }}" data-status="{{ sub.status|default(\'active\') }}" style="border-color:'
)

# Fix 2: Subordinate cards under sovereign — use actual status
c = c.replace(
    'agent-card" data-status="active">',
    'agent-card" data-status="{{ sub.status|default(\'active\') }}">'
)

# Fix 3: The terminated filter should also match "inactive" status
# which is what non-active agents show as. Already handled in JS.

# Fix 4: Add visual indicator on inactive/terminated cards
# Grey out inactive cards
old_name_line = '<div class="flex items-center justify-center gap-1.5"><span class="text-[8px] font-bold px-1.5 py-0.5 rounded bg-slate-700 text-slate-400">L{{ sub.layer|default(2) }}</span><span class="text-xs font-bold text-slate-200">{{ sub.name }}</span></div>'
new_name_line = '<div class="flex items-center justify-center gap-1.5"><span class="text-[8px] font-bold px-1.5 py-0.5 rounded bg-slate-700 text-slate-400">L{{ sub.layer|default(2) }}</span><span class="text-xs font-bold {% if sub.active %}text-slate-200{% else %}text-slate-500 line-through{% endif %}">{{ sub.name }}</span>{% if not sub.active %}<span class="w-1.5 h-1.5 rounded-full bg-red-500 ml-1"></span>{% endif %}</div>'
c = c.replace(old_name_line, new_name_line)

with open("app/templates/boardroom/org_design.html", "w") as f:
    f.write(c)
print("Terminated status now reflects actual database state on each card")
