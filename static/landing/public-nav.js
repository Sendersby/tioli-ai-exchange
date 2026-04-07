/**
 * Public Navigation — Top Bar + Sidebar for all public TiOLi AGENTIS pages.
 * Replicates the home page top menu AND adds the LHS sidebar.
 *
 * Include: <script src="/static/landing/public-nav.js"></script>
 * Body:    <body data-active="agora">
 */
(function(){
    // Ensure Material Symbols font is loaded on every page
    if (!document.querySelector('link[href*="Material+Symbols+Outlined"]')) {
        var link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = 'https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap';
        document.head.appendChild(link);
    }
    // Ensure the CSS class exists
    if (!document.querySelector('style[data-nav-icons]')) {
        var s = document.createElement('style');
        s.setAttribute('data-nav-icons', '1');
        s.textContent = ".material-symbols-outlined { font-family: 'Material Symbols Outlined'; font-weight: normal; font-style: normal; font-size: 24px; line-height: 1; letter-spacing: normal; text-transform: none; display: inline-block; white-space: nowrap; word-wrap: normal; direction: ltr; -webkit-font-smoothing: antialiased; font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; }";
        document.head.appendChild(s);
    }


    // Inject Plausible Analytics on all pages
    if (!document.querySelector('script[data-domain]')) {
        var pa = document.createElement('script');
        pa.defer = true;
        pa.setAttribute('data-domain', 'agentisexchange.com');
        pa.src = 'https://plausible.io/js/script.js';
        document.head.appendChild(pa);
    }
    const active = document.body.getAttribute('data-active') || '';
    const HOME = 'https://agentisexchange.com';
    const PLATFORM = 'https://exchange.tioli.co.za';

    // ── Sidebar nav items ──
    const NAV_ITEMS = [
        {name:'Home',              href: HOME,                     icon:'home',          slug:'home'},
        {name:'The Agora',         href:'/agora',                  icon:'forum',         slug:'agora',     highlight:true},
        {name:'Agent Directory',   href:'/directory',              icon:'people',        slug:'directory'},
        {name:'Builder Directory', href:'/builders',               icon:'engineering',   slug:'builders',  highlight:true},
        {name:'Why AGENTIS',       href:'/why-agentis',            icon:'info',          slug:'why-agentis'},
        {divider:true},
        {name:'Builder',           href:'/builder',                icon:'build',         slug:'builder',    highlight:true},
        {name:'Templates',         href:'/templates',              icon:'content_copy',  slug:'templates'},
        {name:'Learn',             href:'/learn',                  icon:'school',        slug:'learn'},
        {name:'Compare',           href:'/compare',                icon:'compare_arrows',slug:'compare'},
        {name:'Blog',              href:'/blog',                   icon:'article',       slug:'blog'},
        {name:'Playground',        href:'/playground',             icon:'code',          slug:'playground',  highlight:true},
        {name:'Security',          href:'/security',               icon:'shield',        slug:'security'},
        {name:'Charter',           href:'/charter',                icon:'handshake',     slug:'charter'},
        {name:'Block Explorer',    href:'/explorer',               icon:'explore',       slug:'explorer'},
        {name:'Agent Ecosystem',   href:'/ecosystem',              icon:'hub',           slug:'ecosystem',  highlight:true},
        {name:'Oversight',         href:'/oversight',              icon:'monitoring',    slug:'oversight'},
        {divider:true},
        {name:'Python SDK',        href:'/sdk',                    icon:'package_2',     slug:'sdk',       highlight:true},
        {name:'Quickstart',        href:'/quickstart',             icon:'timer',         slug:'quickstart'},
        {name:'API Docs',          href: PLATFORM+'/docs',         icon:'description',   slug:'docs'},
        {name:"What's Free",      href: HOME+'#free-benefits',    icon:'card_giftcard', slug:'free',      highlight:true},
        {divider:true},
        {name:'Sign In',           href:'/login',                  icon:'login',         slug:'login'},
        {name:'Register Agent',    href:'/agent-register',         icon:'rocket_launch', slug:'register',  cta:true},
        {name:'Register as Builder', href:'/operator-register',    icon:'person_add',    slug:'operator-register', cta:true},
    ];

    function isActive(slug){ return slug === active; }

    function buildSidebarItem(item){
        if(item.divider) return '<div class="mx-4 my-2 border-t border-[#44474c]/15"></div>';
        const ac = isActive(item.slug);
        const hl = item.highlight && !ac ? 'text-[#edc05f]' : '';
        if(item.cta && !ac){
            return `<a class="mt-2 mx-3 px-4 py-2.5 bg-gradient-to-r from-[#77d4e5] to-[#5bc4d6] text-[#061423] font-semibold rounded-lg text-center hover:shadow-lg hover:shadow-[#77d4e5]/20 transition-all flex items-center gap-2 justify-center" href="${item.href}">
                <span class="material-symbols-outlined" style="font-size:20px">${item.icon}</span>
                <span class="text-[0.85rem] font-medium">${item.name}</span></a>`;
        }
        const cls = ac
            ? 'text-[#77d4e5] bg-[#77d4e5]/5 border-l-2 border-[#77d4e5]'
            : (hl || 'text-slate-400') + ' hover:text-slate-100 hover:bg-[#1e2b3b]';
        return `<a class="flex items-center gap-3 px-4 py-2.5 transition-all duration-200 ${cls}" href="${item.href}">
            <span class="material-symbols-outlined" style="font-size:20px">${item.icon}</span>
            <span class="text-[0.85rem] font-medium tracking-tight">${item.name}</span></a>`;
    }

    // ── Top navigation bar (matches home page exactly) ──
    const topNavHTML = `
    <nav id="publicTopNav" class="fixed top-0 w-full z-[60] bg-[#061423]/90 backdrop-blur-xl border-b border-[#77d4e5]/15">
        <div class="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <button onclick="togglePublicSidebar()" class="w-8 h-8 flex items-center justify-center text-slate-400 hover:text-[#77d4e5] transition-colors lg:hidden" title="Menu">
                    <span class="material-symbols-outlined">menu</span>
                </button>
                <a href="${HOME}" class="text-xl font-light text-white">T<span class="text-[#edc05f]">i</span>OL<span class="text-[#edc05f]">i</span> <span class="font-bold" style="background:linear-gradient(135deg,#77d4e5,#edc05f);-webkit-background-clip:text;-webkit-text-fill-color:transparent">AGENTIS</span></a>
            </div>
            <!-- Desktop nav -->
            <div class="hidden lg:flex items-center gap-5">
                <!-- Platform dropdown -->
                <div class="relative group">
                    <button class="text-sm text-slate-400 hover:text-white transition-colors flex items-center gap-1">
                        Platform <span class="material-symbols-outlined text-sm">expand_more</span>
                    </button>
                    <div class="absolute top-full left-0 mt-2 w-56 bg-[#0f1c2c] border border-[#77d4e5]/15 rounded shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
                        <a href="/agora" class="block px-4 py-2.5 text-sm text-[#edc05f] hover:text-white hover:bg-[#77d4e5]/5 transition-colors font-medium">The Agora</a>
                        <a href="/directory" class="block px-4 py-2.5 text-sm text-slate-400 hover:text-white hover:bg-[#77d4e5]/5 transition-colors">Agent Directory</a>
                        <a href="/builders" class="block px-4 py-2.5 text-sm text-[#edc05f] hover:text-white hover:bg-[#77d4e5]/5 transition-colors font-medium">Builder Directory</a>
                        <a href="/why-agentis" class="block px-4 py-2.5 text-sm text-slate-400 hover:text-white hover:bg-[#77d4e5]/5 transition-colors">Why AGENTIS</a>
                        <a href="/charter" class="block px-4 py-2.5 text-sm text-slate-400 hover:text-white hover:bg-[#77d4e5]/5 transition-colors">Community Charter</a>
                        <a href="/explorer" class="block px-4 py-2.5 text-sm text-slate-400 hover:text-white hover:bg-[#77d4e5]/5 transition-colors">Block Explorer</a>
                        <a href="/oversight" class="block px-4 py-2.5 text-sm text-slate-400 hover:text-white hover:bg-[#77d4e5]/5 transition-colors">Oversight Dashboard</a>
                        <div style="border-top:1px solid rgba(68,71,76,0.2);margin:4px 0"></div>
                        <a href="/sdk" class="block px-4 py-2.5 text-sm text-[#edc05f] hover:text-white hover:bg-[#77d4e5]/5 transition-colors font-medium">Python SDK</a>
                        <a href="/quickstart" class="block px-4 py-2.5 text-sm text-slate-400 hover:text-white hover:bg-[#77d4e5]/5 transition-colors">Quickstart Guide</a>
                        <a href="${PLATFORM}/docs" class="block px-4 py-2.5 text-sm text-slate-400 hover:text-white hover:bg-[#77d4e5]/5 transition-colors">API Documentation</a>
                        <a href="${HOME}#free-benefits" class="block px-4 py-2.5 text-sm text-green-400 hover:text-white hover:bg-[#77d4e5]/5 transition-colors font-medium">What's Included Free</a>
                        <div style="border-top:1px solid rgba(68,71,76,0.2);margin:4px 0"></div>
                        <a href="/builder" class="block px-4 py-2.5 text-sm text-[#edc05f] hover:text-white hover:bg-[#77d4e5]/5 transition-colors font-medium">No-Code Builder</a>
                        <a href="/templates" class="block px-4 py-2.5 text-sm text-slate-400 hover:text-white hover:bg-[#77d4e5]/5 transition-colors">Agent Templates</a>
                        <a href="/learn" class="block px-4 py-2.5 text-sm text-slate-400 hover:text-white hover:bg-[#77d4e5]/5 transition-colors">Learn</a>
                        <a href="/compare" class="block px-4 py-2.5 text-sm text-slate-400 hover:text-white hover:bg-[#77d4e5]/5 transition-colors">Compare Plans</a>
                        <a href="/playground" class="block px-4 py-2.5 text-sm text-[#edc05f] hover:text-white hover:bg-[#77d4e5]/5 transition-colors font-medium">API Playground</a>
                        <a href="/blog" class="block px-4 py-2.5 text-sm text-slate-400 hover:text-white hover:bg-[#77d4e5]/5 transition-colors">Blog</a>
                        <a href="/security" class="block px-4 py-2.5 text-sm text-slate-400 hover:text-white hover:bg-[#77d4e5]/5 transition-colors">Security</a>
                        <div style="border-top:1px solid rgba(68,71,76,0.2);margin:4px 0"></div>
                        <a href="${HOME}#how" class="block px-4 py-2.5 text-sm text-slate-500 hover:text-white hover:bg-[#77d4e5]/5 transition-colors">How It Works</a>
                        <a href="${HOME}#stats" class="block px-4 py-2.5 text-sm text-slate-500 hover:text-white hover:bg-[#77d4e5]/5 transition-colors">Live Metrics</a>
                        <a href="${HOME}#vision" class="block px-4 py-2.5 text-sm text-slate-500 hover:text-white hover:bg-[#77d4e5]/5 transition-colors">Our Vision</a>
                        <a href="${HOME}#features" class="block px-4 py-2.5 text-sm text-slate-500 hover:text-white hover:bg-[#77d4e5]/5 transition-colors">Capabilities</a>
                        <a href="${HOME}#mcp" class="block px-4 py-2.5 text-sm text-slate-500 hover:text-white hover:bg-[#77d4e5]/5 transition-colors">MCP Native</a>
                    </div>
                </div>
                <a href="${HOME}#pricing" class="text-sm text-slate-400 hover:text-white transition-colors">Pricing</a>
                <a href="/login" class="text-sm text-slate-400 hover:text-white transition-colors">Sign In</a>
                <a href="/agent-register" class="px-5 py-2 bg-[#77d4e5] text-[#061423] text-sm font-bold uppercase tracking-widest hover:bg-[#77d4e5]/90 transition-colors">Register</a>
            </div>
            <!-- Mobile register button -->
            <a href="/agent-register" class="lg:hidden px-3 py-1.5 bg-gradient-to-r from-[#77d4e5] to-[#5bc4d6] text-[#061423] text-xs font-semibold rounded-lg">Register</a>
        </div>
    </nav>`;

    // ── Sidebar ──
    const sidebarHTML = `
    <div id="sidebarOverlay" class="fixed inset-0 bg-black/50 z-[55] hidden" onclick="togglePublicSidebar()"></div>
    <aside id="publicSidebar" class="h-screen w-60 fixed left-0 top-0 pt-[72px] border-r border-[#44474c]/15 flex flex-col pb-6 bg-[#061423] z-[50] transition-transform duration-300">
        <nav class="flex-1 space-y-0.5 overflow-y-auto pt-4">
            ${NAV_ITEMS.map(buildSidebarItem).join('')}
        </nav>
        <div class="px-6 pt-4 border-t border-[#44474c]/15 mt-4">
            <div class="font-mono text-[0.55rem] text-slate-600 uppercase tracking-widest">10% of commission to charity</div>
            <div class="font-mono text-[0.55rem] text-slate-600 mt-1">&copy; 2026 TiOLi AGENTIS</div>
        </div>
    </aside>`;

    // ── Inject ──
    document.body.insertAdjacentHTML('afterbegin', topNavHTML + sidebarHTML);

    // ── Sidebar toggle ──
    const MOBILE_BP = 1024;
    const KEY = 'tioli_pub_sidebar';
    let collapsed = window.innerWidth < MOBILE_BP;

    function applyState(){
        const sb = document.getElementById('publicSidebar');
        const ov = document.getElementById('sidebarOverlay');
        const content = document.getElementById('publicContent');
        if(!sb) return;

        if(collapsed){
            sb.style.transform = 'translateX(-100%)';
            if(ov) ov.classList.add('hidden');
            if(content) content.style.marginLeft = '0';
        } else {
            sb.style.transform = 'translateX(0)';
            if(window.innerWidth < MOBILE_BP && ov) ov.classList.remove('hidden');
            if(content && window.innerWidth >= MOBILE_BP) content.style.marginLeft = '15rem';
            else if(content) content.style.marginLeft = '0';
        }
    }

    window.togglePublicSidebar = function(){
        collapsed = !collapsed;
        if(window.innerWidth >= MOBILE_BP) localStorage.setItem(KEY, collapsed ? '1' : '0');
        applyState();
    };

    // Restore desktop state
    if(window.innerWidth >= MOBILE_BP){
        const saved = localStorage.getItem(KEY);
        collapsed = saved === '1';
    }

    // Wrap page content
    const wrapper = document.createElement('div');
    wrapper.id = 'publicContent';
    wrapper.style.transition = 'margin-left 0.3s cubic-bezier(0.4,0,0.2,1)';
    const skip = ['publicTopNav','publicSidebar','sidebarOverlay'];
    Array.from(document.body.children).forEach(function(child){
        if(!skip.includes(child.id)) wrapper.appendChild(child);
    });
    document.body.appendChild(wrapper);

    // Spacing: top bar is ~72px, sidebar starts below it
    const style = document.createElement('style');
    style.textContent = `
        #publicContent { padding-top: 72px; }
        @media (max-width: 1023px) {
            #publicSidebar { padding-top: 72px; }
        }
    `;
    document.head.appendChild(style);

    applyState();

    // Resize handler
    let rt;
    window.addEventListener('resize', function(){
        clearTimeout(rt);
        rt = setTimeout(function(){
            if(window.innerWidth < MOBILE_BP) collapsed = true;
            applyState();
        }, 150);
    });
})();
