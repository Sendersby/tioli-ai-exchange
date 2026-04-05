"""Fix filter defaults — terminated OFF by default, add status lights."""

with open("app/templates/boardroom/org_design.html") as f:
    c = f.read()

# 1. Fix terminated button default — should be dimmed/off on load
old_term = '<button onclick="toggleFilter(\'terminated\')" id="f-terminated" class="filter-btn px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-slate-700/30 text-slate-500 border-slate-600">Terminated</button>'
new_term = '<button onclick="toggleFilter(\'terminated\')" id="f-terminated" class="filter-btn px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-slate-700/30 text-slate-500 border-slate-600" style="opacity:0.4">Terminated<span id="light-terminated" class="inline-block w-2 h-2 rounded-full bg-red-500 ml-1.5 align-middle"></span></button>'

c = c.replace(old_term, new_term)

# 2. Add green/red lights to Active, Paused, and System buttons too
old_active = '<button onclick="toggleFilter(\'active\')" id="f-active" class="filter-btn active-filter px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-emerald-500/10 text-emerald-400 border-emerald-500/30">Active</button>'
new_active = '<button onclick="toggleFilter(\'active\')" id="f-active" class="filter-btn active-filter px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-emerald-500/10 text-emerald-400 border-emerald-500/30">Active<span id="light-active" class="inline-block w-2 h-2 rounded-full bg-emerald-400 ml-1.5 align-middle"></span></button>'
c = c.replace(old_active, new_active)

old_paused = '<button onclick="toggleFilter(\'paused\')" id="f-paused" class="filter-btn active-filter px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-amber-500/10 text-amber-400 border-amber-500/30">Paused</button>'
new_paused = '<button onclick="toggleFilter(\'paused\')" id="f-paused" class="filter-btn active-filter px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-amber-500/10 text-amber-400 border-amber-500/30">Paused<span id="light-paused" class="inline-block w-2 h-2 rounded-full bg-emerald-400 ml-1.5 align-middle"></span></button>'
c = c.replace(old_paused, new_paused)

old_system = '<button onclick="toggleFilter(\'system\')" id="f-system" class="filter-btn active-filter px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-slate-700/30 text-slate-400 border-slate-600">System</button>'
new_system = '<button onclick="toggleFilter(\'system\')" id="f-system" class="filter-btn active-filter px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-slate-700/30 text-slate-400 border-slate-600">System<span id="light-system" class="inline-block w-2 h-2 rounded-full bg-emerald-400 ml-1.5 align-middle"></span></button>'
c = c.replace(old_system, new_system)

# 3. Update the toggleFilter JS to change light colour
old_toggle_fn = """function toggleFilter(type) {
  activeFilters[type] = !activeFilters[type];
  const btn = document.getElementById('f-' + type);
  btn.style.opacity = activeFilters[type] ? '1' : '0.4';
  if (activeFilters[type]) btn.classList.add('active-filter');
  else btn.classList.remove('active-filter');
  applyAllFilters();
}"""

new_toggle_fn = """function toggleFilter(type) {
  activeFilters[type] = !activeFilters[type];
  const btn = document.getElementById('f-' + type);
  const light = document.getElementById('light-' + type);
  btn.style.opacity = activeFilters[type] ? '1' : '0.4';
  if (activeFilters[type]) {
    btn.classList.add('active-filter');
    if (light) { light.classList.remove('bg-red-500'); light.classList.add('bg-emerald-400'); }
  } else {
    btn.classList.remove('active-filter');
    if (light) { light.classList.remove('bg-emerald-400'); light.classList.add('bg-red-500'); }
  }
  applyAllFilters();
}"""

c = c.replace(old_toggle_fn, new_toggle_fn)

# 4. Run applyAllFilters on page load to hide terminated by default
if "DOMContentLoaded" not in c and "applyAllFilters();" not in c.split("</script>")[0][-200:]:
    c = c.replace(
        "</script>",
        "// Apply filters on load to hide terminated by default\napplyAllFilters();\n</script>"
    )

with open("app/templates/boardroom/org_design.html", "w") as f:
    f.write(c)
print("Filters fixed: terminated OFF by default, green/red lights on all toggles")
