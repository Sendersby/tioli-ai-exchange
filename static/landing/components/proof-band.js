/**
 * proof-band.js — Workstream B from COMPETITOR_ADOPTION_PLAN.md v1.1
 *
 * Self-contained vanilla JS proof-by-numbers component. Drop a
 * <div id="proof-band"></div> on any landing page and include this script.
 * Fetches /api/v1/public/proof-metrics, animates a 6-metric horizontal band.
 *
 * Standing rules:
 * - No framework dependency (works on any TiOLi page regardless of Tailwind etc.)
 * - Public read-only API, no PII
 * - Graceful degradation if API fails (renders nothing, no errors thrown)
 *
 * Usage:
 *   <div id="proof-band"></div>
 *   <script src="/static/landing/components/proof-band.js?v=1776140000"></script>
 */
(function () {
    var TARGET_ID = 'proof-band';
    var API_URL = '/api/v1/public/proof-metrics';
    var ANIM_DURATION_MS = 1400;
    var ANIM_FPS = 60;

    var STYLE = [
        '.proof-band-wrap{margin:24px 0 32px;font-family:Inter,system-ui,sans-serif;}',
        '.proof-band-heading{font-size:11px;text-transform:uppercase;letter-spacing:1.2px;color:#94a3b8;margin-bottom:10px;text-align:center;}',
        '.proof-band-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;max-width:1100px;margin:0 auto;}',
        '@media(min-width:768px){.proof-band-grid{grid-template-columns:repeat(3,1fr);}}',
        '@media(min-width:1100px){.proof-band-grid{grid-template-columns:repeat(6,1fr);gap:8px;}}',
        '.proof-band-card{background:#0f1c2c;border:1px solid rgba(119,212,229,0.15);border-radius:10px;padding:14px 12px;text-align:center;transition:border-color .2s,transform .2s;cursor:default;}',
        '.proof-band-card:hover{border-color:rgba(119,212,229,0.45);transform:translateY(-1px);}',
        '.proof-band-value{font-size:26px;font-weight:800;color:#77d4e5;line-height:1.05;font-variant-numeric:tabular-nums;}',
        '.proof-band-label{font-size:10.5px;color:#94a3b8;margin-top:6px;line-height:1.3;}',
        '.proof-band-suffix{font-size:10px;color:#64748b;margin-top:2px;}',
        '.proof-band-footer{font-size:10px;color:#64748b;text-align:center;margin-top:10px;}',
        '.proof-band-footer a{color:#77d4e5;text-decoration:none;}',
        '.proof-band-footer a:hover{text-decoration:underline;}'
    ].join('');

    function injectStyle() {
        if (document.getElementById('proof-band-style')) return;
        var s = document.createElement('style');
        s.id = 'proof-band-style';
        s.textContent = STYLE;
        document.head.appendChild(s);
    }

    function formatValue(value, type) {
        if (value === null || value === undefined) return '—';
        if (type === 'currency_zar') {
            if (value >= 1000000) return 'R' + (value / 1000000).toFixed(1) + 'M';
            if (value >= 1000) return 'R' + (value / 1000).toFixed(1) + 'K';
            return 'R' + value.toFixed(2);
        }
        if (type === 'hours') {
            if (value === 0) return 'live';
            if (value < 1) return Math.round(value * 60) + 'm fresh';
            return value.toFixed(1) + 'h fresh';
        }
        // integer
        if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
        if (value >= 10000) return (value / 1000).toFixed(1) + 'K';
        if (value >= 1000) return value.toLocaleString();
        return Math.round(value).toString();
    }

    function animateCount(el, finalValue, format) {
        if (typeof finalValue !== 'number') {
            el.textContent = formatValue(finalValue, format);
            return;
        }
        var startTs = null;
        var frameCount = Math.round(ANIM_DURATION_MS / 1000 * ANIM_FPS);
        var current = 0;
        function step(ts) {
            if (!startTs) startTs = ts;
            var elapsed = ts - startTs;
            var progress = Math.min(elapsed / ANIM_DURATION_MS, 1);
            // ease-out cubic
            var eased = 1 - Math.pow(1 - progress, 3);
            current = finalValue * eased;
            el.textContent = formatValue(current, format);
            if (progress < 1) requestAnimationFrame(step);
            else el.textContent = formatValue(finalValue, format);
        }
        requestAnimationFrame(step);
    }

    function render(target, payload) {
        var headline = (payload && payload.headline_six) || [];
        if (!headline.length) {
            target.innerHTML = '';
            return;
        }
        var refreshedAt = payload.refreshed_at ? new Date(payload.refreshed_at) : null;
        var refreshedLabel = refreshedAt
            ? 'Refreshed ' + refreshedAt.toLocaleString() + ' · cached 5 min'
            : 'Live from on-chain data · cached 5 min';

        var html = '<div class="proof-band-wrap">';
        html += '<div class="proof-band-heading">The exchange in numbers — refreshed every 5 minutes from on-chain data</div>';
        html += '<div class="proof-band-grid">';
        for (var i = 0; i < headline.length; i++) {
            var m = headline[i];
            var safeKey = String(m.key || ('m' + i)).replace(/[^a-z0-9_-]/gi, '');
            html += '<div class="proof-band-card" title="' + refreshedLabel + '">';
            html += '<div class="proof-band-value" data-pb-value="' + safeKey + '" data-pb-format="' + (m.format || 'integer') + '">0</div>';
            html += '<div class="proof-band-label">' + (m.label || '') + '</div>';
            if (m.suffix) html += '<div class="proof-band-suffix">' + m.suffix + '</div>';
            html += '</div>';
        }
        html += '</div>';
        html += '<div class="proof-band-footer">' + refreshedLabel + ' · <a href="/api/v1/public/proof-metrics" target="_blank">view raw JSON</a> · <a href="/trust">trust centre</a></div>';
        html += '</div>';
        target.innerHTML = html;

        // Kick off animation per card
        for (var j = 0; j < headline.length; j++) {
            var m2 = headline[j];
            var safeKey2 = String(m2.key || ('m' + j)).replace(/[^a-z0-9_-]/gi, '');
            var el = target.querySelector('[data-pb-value="' + safeKey2 + '"]');
            if (el) animateCount(el, m2.value, m2.format || 'integer');
        }
    }

    function getOrCreateTarget() {
        var existing = document.getElementById(TARGET_ID);
        if (existing) return existing;
        var target = document.createElement('div');
        target.id = TARGET_ID;
        // Insertion preference: explicit hero anchor > first <main> > first <section> after nav > top of body
        var anchor = document.querySelector('[data-proof-band-anchor]')
                  || document.querySelector('main')
                  || document.querySelector('section');
        if (anchor && anchor.parentNode) {
            anchor.parentNode.insertBefore(target, anchor.nextSibling);
        } else if (document.body && document.body.firstElementChild) {
            document.body.insertBefore(target, document.body.firstElementChild);
        } else if (document.body) {
            document.body.appendChild(target);
        }
        return target;
    }

    function init() {
        var target = getOrCreateTarget();
        if (!target) return;
        injectStyle();
        try {
            fetch(API_URL, { credentials: 'omit' })
                .then(function (r) {
                    if (!r.ok) throw new Error('proof-metrics HTTP ' + r.status);
                    return r.json();
                })
                .then(function (payload) { render(target, payload); })
                .catch(function (err) {
                    if (window.console) console.warn('[proof-band]', err);
                    target.innerHTML = '';
                });
        } catch (err) {
            if (window.console) console.warn('[proof-band] fatal', err);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
