"""Add green/red indicator lights to layer toggle buttons and ensure all toggles work."""

with open("app/templates/boardroom/org_design.html") as f:
    c = f.read()

# Add lights to L0-L3 buttons
c = c.replace(
    '''id="l-0" class="level-btn active-level px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-[#D4A94A]/10 text-[#D4A94A] border-[#D4A94A]/30">L0 Founder</button>''',
    '''id="l-0" class="level-btn active-level px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-[#D4A94A]/10 text-[#D4A94A] border-[#D4A94A]/30">L0 Founder<span id="light-l-0" class="inline-block w-2 h-2 rounded-full bg-emerald-400 ml-1.5 align-middle"></span></button>'''
)

c = c.replace(
    '''id="l-1" class="level-btn active-level px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-[#028090]/10 text-[#028090] border-[#028090]/30">L1 Arch</button>''',
    '''id="l-1" class="level-btn active-level px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-[#028090]/10 text-[#028090] border-[#028090]/30">L1 Arch<span id="light-l-1" class="inline-block w-2 h-2 rounded-full bg-emerald-400 ml-1.5 align-middle"></span></button>'''
)

c = c.replace(
    '''id="l-2" class="level-btn active-level px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-[#77d4e5]/10 text-[#77d4e5] border-[#77d4e5]/30">L2 Domain</button>''',
    '''id="l-2" class="level-btn active-level px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-[#77d4e5]/10 text-[#77d4e5] border-[#77d4e5]/30">L2 Domain<span id="light-l-2" class="inline-block w-2 h-2 rounded-full bg-emerald-400 ml-1.5 align-middle"></span></button>'''
)

c = c.replace(
    '''id="l-3" class="level-btn active-level px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-slate-500/10 text-slate-400 border-slate-500/30">L3 Ops</button>''',
    '''id="l-3" class="level-btn active-level px-3 py-1.5 rounded-full text-xs font-bold border transition-all bg-slate-500/10 text-slate-400 border-slate-500/30">L3 Ops<span id="light-l-3" class="inline-block w-2 h-2 rounded-full bg-emerald-400 ml-1.5 align-middle"></span></button>'''
)

# Update toggleLevel JS to change light colour
old_toggle_level = """function toggleLevel(level) {
  activeLevels[level] = !activeLevels[level];
  const btn = document.getElementById('l-' + level);
  if (activeLevels[level]) { btn.classList.add('active-level'); btn.style.opacity = '1'; }
  else { btn.classList.remove('active-level'); btn.style.opacity = '0.3'; }
  applyAllFilters();
}"""

new_toggle_level = """function toggleLevel(level) {
  activeLevels[level] = !activeLevels[level];
  const btn = document.getElementById('l-' + level);
  const light = document.getElementById('light-l-' + level);
  if (activeLevels[level]) {
    btn.classList.add('active-level');
    btn.style.opacity = '1';
    if (light) { light.classList.remove('bg-red-500'); light.classList.add('bg-emerald-400'); }
  } else {
    btn.classList.remove('active-level');
    btn.style.opacity = '0.3';
    if (light) { light.classList.remove('bg-emerald-400'); light.classList.add('bg-red-500'); }
  }
  applyAllFilters();
}"""

c = c.replace(old_toggle_level, new_toggle_level)

# Update toggleAllLevels to also update lights
old_all = """function toggleAllLevels(show) {
  for (let i = 0; i <= 3; i++) {
    activeLevels[i] = show;
    const btn = document.getElementById('l-' + i);
    if (btn) { btn.style.opacity = show ? '1' : '0.3'; if (show) btn.classList.add('active-level'); else btn.classList.remove('active-level'); }
  }
  applyAllFilters();
}"""

new_all = """function toggleAllLevels(show) {
  for (let i = 0; i <= 3; i++) {
    activeLevels[i] = show;
    const btn = document.getElementById('l-' + i);
    const light = document.getElementById('light-l-' + i);
    if (btn) {
      btn.style.opacity = show ? '1' : '0.3';
      if (show) btn.classList.add('active-level'); else btn.classList.remove('active-level');
    }
    if (light) {
      if (show) { light.classList.remove('bg-red-500'); light.classList.add('bg-emerald-400'); }
      else { light.classList.remove('bg-emerald-400'); light.classList.add('bg-red-500'); }
    }
  }
  applyAllFilters();
}"""

c = c.replace(old_all, new_all)

with open("app/templates/boardroom/org_design.html", "w") as f:
    f.write(c)
print("All toggle lights added — status + layer buttons all have green/red indicators")
