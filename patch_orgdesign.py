"""Patch organogram — add level toggles and data-level attributes."""

with open("app/templates/boardroom/org_design.html") as f:
    content = f.read()

# 1. Add level toggle buttons after status filters
old_zoom = '      <span class="text-slate-600 mx-2">|</span>\n      <button onclick="setZoom(\'normal\')"'
new_zoom = """    </div>
    <div class="flex flex-wrap justify-center gap-2 mb-4">
      <span class="text-xs text-slate-500 self-center mr-1">Layers:</span>
      <button onclick="toggleLevel(0)" id="l-0" class="level-btn active-level px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-[#D4A94A]/10 text-[#D4A94A] border-[#D4A94A]/30">L0 Founder</button>
      <button onclick="toggleLevel(1)" id="l-1" class="level-btn active-level px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-[#028090]/10 text-[#028090] border-[#028090]/30">L1 Arch</button>
      <button onclick="toggleLevel(2)" id="l-2" class="level-btn active-level px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-[#77d4e5]/10 text-[#77d4e5] border-[#77d4e5]/30">L2 Domain</button>
      <button onclick="toggleLevel(3)" id="l-3" class="level-btn active-level px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-slate-500/10 text-slate-400 border-slate-500/30">L3 Ops</button>
      <span class="text-slate-600 mx-1">|</span>
      <button onclick="toggleAllLevels(true)" class="text-[10px] text-slate-500 hover:text-white px-1">All</button>
      <button onclick="toggleAllLevels(false)" class="text-[10px] text-slate-500 hover:text-white px-1">None</button>
    </div>
    <div class="flex flex-wrap justify-center gap-2 mb-8">
      <span class="text-xs text-slate-500 self-center mr-1">Zoom:</span>
      <button onclick="setZoom('normal')\""""

content = content.replace(old_zoom, new_zoom)

# 2. Add data-level="0" to founder card
content = content.replace(
    'bg-gradient-to-r from-[#D4A94A] to-[#edc05f] text-[#0D1B2A] px-10 py-5',
    'bg-gradient-to-r from-[#D4A94A] to-[#edc05f] text-[#0D1B2A] px-10 py-5" data-level="0'
)

# 3. Add data-level="1" to sovereign card
content = content.replace(
    'block border-2 border-[#D4A94A]/50 bg-[#1B2838] px-8 py-4',
    'block border-2 border-[#D4A94A]/50 bg-[#1B2838] px-8 py-4" data-level="1'
)

# 4. Add data-level="1" to arch agent cards
content = content.replace(
    'block border rounded-xl p-4 text-center w-full transition-all hover:shadow-lg"',
    'block border rounded-xl p-4 text-center w-full transition-all hover:shadow-lg" data-level="1"'
)

# 5. Add data-level to subordinate cards based on their layer
content = content.replace(
    'agent-card" style="border-color:',
    'agent-card" data-level="{{ sub.layer|default(2) }}" style="border-color:'
)

# 6. Add level toggle JS
old_js_start = "const activeFilters = {active: true, paused: true, terminated: false, system: true};"
new_js_start = """const activeFilters = {active: true, paused: true, terminated: false, system: true};
const activeLevels = {0: true, 1: true, 2: true, 3: true};

function toggleLevel(level) {
  activeLevels[level] = !activeLevels[level];
  const btn = document.getElementById('l-' + level);
  if (activeLevels[level]) { btn.classList.add('active-level'); btn.style.opacity = '1'; }
  else { btn.classList.remove('active-level'); btn.style.opacity = '0.3'; }
  applyAllFilters();
}

function toggleAllLevels(show) {
  for (let i = 0; i <= 3; i++) {
    activeLevels[i] = show;
    const btn = document.getElementById('l-' + i);
    if (btn) { btn.style.opacity = show ? '1' : '0.3'; if (show) btn.classList.add('active-level'); else btn.classList.remove('active-level'); }
  }
  applyAllFilters();
}

function applyAllFilters() {
  // Apply level filters
  document.querySelectorAll('[data-level]').forEach(el => {
    const level = parseInt(el.dataset.level);
    if (!isNaN(level)) el.style.display = activeLevels[level] ? '' : 'none';
  });
  // Apply status filters
  document.querySelectorAll('.agent-card').forEach(card => {
    const status = (card.dataset.status || 'active').toLowerCase();
    if (status === 'active' && !activeFilters.active) card.style.display = 'none';
    else if (status === 'paused' && !activeFilters.paused) card.style.display = 'none';
    else if (status === 'terminated' && !activeFilters.terminated) card.style.display = 'none';
  });
  const sys = document.querySelector('.system-section');
  if (sys) sys.style.display = activeFilters.system ? '' : 'none';
}"""

content = content.replace(old_js_start, new_js_start)

# 7. Update applyFilters to use applyAllFilters
content = content.replace("applyFilters();", "applyAllFilters();")

# 8. Remove old applyFilters function (replaced by applyAllFilters)
content = content.replace(
    """function applyFilters() {
  document.querySelectorAll('.agent-card').forEach(card => {
    const status = (card.dataset.status || 'active').toLowerCase();
    if (status === 'active' && !activeFilters.active) card.style.display = 'none';
    else if (status === 'paused' && !activeFilters.paused) card.style.display = 'none';
    else if (status === 'terminated' && !activeFilters.terminated) card.style.display = 'none';
    else card.style.display = '';
  });
  const sys = document.querySelector('.system-section');
  if (sys) sys.style.display = activeFilters.system ? '' : 'none';
}""",
    "// applyFilters replaced by applyAllFilters above"
)

with open("app/templates/boardroom/org_design.html", "w") as f:
    f.write(content)
print("Organogram patched with level toggles + data-level attributes")
