/**
 * feedback-modal.js — Workstream C from COMPETITOR_ADOPTION_PLAN.md v1.1
 *
 * Self-contained vanilla JS feedback modal. Activates on click of any
 * element with class="js-feedback-trigger" (typically a footer link).
 *
 * Standing rules:
 * - Submits to /api/v1/feedback which delivers to founder inbox (rule #4)
 * - No framework dependency
 * - Honeypot field for bot deflection
 * - Captures page URL automatically
 *
 * Usage:
 *   <a href="#" class="js-feedback-trigger">Report feedback</a>
 *   <script src="/static/landing/components/feedback-modal.js?v=1776140000"></script>
 */
(function () {
    var API_URL = '/api/v1/feedback';
    var MODAL_ID = 'tioli-feedback-modal';

    var STYLE = [
        '.tfm-overlay{position:fixed;inset:0;background:rgba(6,20,35,0.85);display:none;align-items:center;justify-content:center;z-index:100000;font-family:Inter,system-ui,sans-serif;}',
        '.tfm-overlay.tfm-open{display:flex;}',
        '.tfm-modal{background:#0f1c2c;border:1px solid rgba(119,212,229,0.3);border-radius:14px;padding:28px;max-width:480px;width:calc(100% - 40px);max-height:90vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,0.5);}',
        '.tfm-heading{color:#fff;font-size:20px;font-weight:700;margin:0 0 6px;}',
        '.tfm-sub{color:#94a3b8;font-size:13px;margin:0 0 18px;}',
        '.tfm-row{margin-bottom:14px;}',
        '.tfm-label{display:block;font-size:11px;text-transform:uppercase;letter-spacing:0.8px;color:#94a3b8;margin-bottom:6px;}',
        '.tfm-input,.tfm-select,.tfm-textarea{width:100%;background:#061423;color:#d6e4f9;border:1px solid rgba(119,212,229,0.2);border-radius:8px;padding:10px 12px;font-size:14px;font-family:inherit;box-sizing:border-box;}',
        '.tfm-input:focus,.tfm-select:focus,.tfm-textarea:focus{outline:none;border-color:#77d4e5;}',
        '.tfm-textarea{min-height:120px;resize:vertical;}',
        '.tfm-charcount{font-size:11px;color:#64748b;text-align:right;margin-top:4px;}',
        '.tfm-actions{display:flex;justify-content:space-between;align-items:center;margin-top:18px;gap:12px;}',
        '.tfm-cancel{background:transparent;color:#94a3b8;border:none;font-size:13px;cursor:pointer;padding:10px 16px;}',
        '.tfm-cancel:hover{color:#fff;}',
        '.tfm-submit{background:#77d4e5;color:#061423;border:none;border-radius:8px;font-weight:700;font-size:14px;padding:11px 22px;cursor:pointer;transition:transform .1s;}',
        '.tfm-submit:hover{transform:translateY(-1px);}',
        '.tfm-submit:disabled{opacity:0.5;cursor:not-allowed;transform:none;}',
        '.tfm-success{background:#0f1c2c;border:1px solid rgba(74,222,128,0.4);border-radius:10px;padding:18px;color:#4ade80;font-size:14px;margin-top:14px;}',
        '.tfm-error{background:#0f1c2c;border:1px solid rgba(248,113,113,0.4);border-radius:10px;padding:14px;color:#f87171;font-size:13px;margin-top:14px;}',
        '.tfm-honeypot{position:absolute;left:-9999px;opacity:0;pointer-events:none;}',
        '.tfm-rule{font-size:11px;color:#64748b;margin-top:8px;}'
    ].join('');

    function injectStyle() {
        if (document.getElementById('tfm-style')) return;
        var s = document.createElement('style');
        s.id = 'tfm-style';
        s.textContent = STYLE;
        document.head.appendChild(s);
    }

    function buildModal() {
        if (document.getElementById(MODAL_ID)) return;
        var overlay = document.createElement('div');
        overlay.className = 'tfm-overlay';
        overlay.id = MODAL_ID;
        overlay.innerHTML = [
            '<div class="tfm-modal" role="dialog" aria-labelledby="tfm-title">',
            '  <h2 class="tfm-heading" id="tfm-title">Saw something? Tell the founder.</h2>',
            '  <p class="tfm-sub">Stephen reads every feedback submission. No follow-up unless you ask.</p>',
            '  <form id="tfm-form" novalidate>',
            '    <div class="tfm-row">',
            '      <label class="tfm-label" for="tfm-cat">Type</label>',
            '      <select class="tfm-select" id="tfm-cat" name="category" required>',
            '        <option value="bug">Bug or broken thing</option>',
            '        <option value="feature">Feature request or idea</option>',
            '        <option value="compliance">Compliance, security, or privacy concern</option>',
            '        <option value="other">Something else</option>',
            '      </select>',
            '    </div>',
            '    <div class="tfm-row">',
            '      <label class="tfm-label" for="tfm-text">What\'s on your mind?</label>',
            '      <textarea class="tfm-textarea" id="tfm-text" name="text" required minlength="5" maxlength="2000" placeholder="Tell us what\'s broken, what\'s missing, or what\'s brilliant."></textarea>',
            '      <div class="tfm-charcount"><span id="tfm-count">0</span>/2000</div>',
            '    </div>',
            '    <div class="tfm-row">',
            '      <label class="tfm-label" for="tfm-email">Your email (optional)</label>',
            '      <input class="tfm-input" id="tfm-email" name="email" type="email" placeholder="leave blank to stay anonymous">',
            '    </div>',
            '    <input class="tfm-honeypot" id="tfm-website" name="website" type="text" tabindex="-1" autocomplete="off" aria-hidden="true">',
            '    <p class="tfm-rule">Adult or explicit content is not allowed.</p>',
            '    <div class="tfm-actions">',
            '      <button type="button" class="tfm-cancel" id="tfm-cancel">Cancel</button>',
            '      <button type="submit" class="tfm-submit" id="tfm-submit">Send to founder</button>',
            '    </div>',
            '    <div id="tfm-result"></div>',
            '  </form>',
            '</div>'
        ].join('');
        document.body.appendChild(overlay);

        // wire interactions
        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) closeModal();
        });
        document.getElementById('tfm-cancel').addEventListener('click', closeModal);
        document.getElementById('tfm-text').addEventListener('input', function (e) {
            document.getElementById('tfm-count').textContent = e.target.value.length;
        });
        document.getElementById('tfm-form').addEventListener('submit', handleSubmit);
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closeModal();
        });
    }

    function openModal() {
        buildModal();
        var m = document.getElementById(MODAL_ID);
        if (m) m.classList.add('tfm-open');
        var t = document.getElementById('tfm-text');
        if (t) setTimeout(function () { t.focus(); }, 50);
    }

    function closeModal() {
        var m = document.getElementById(MODAL_ID);
        if (m) m.classList.remove('tfm-open');
    }

    function showResult(html, isError) {
        var r = document.getElementById('tfm-result');
        if (!r) return;
        r.innerHTML = '<div class="' + (isError ? 'tfm-error' : 'tfm-success') + '">' + html + '</div>';
    }

    function handleSubmit(e) {
        e.preventDefault();
        var cat = document.getElementById('tfm-cat').value;
        var txt = document.getElementById('tfm-text').value.trim();
        var email = document.getElementById('tfm-email').value.trim();
        var honeypot = document.getElementById('tfm-website').value;

        if (honeypot) {
            // bot
            showResult('Received. Thanks!', false);
            return;
        }
        if (txt.length < 5) {
            showResult('Please give us at least a few words.', true);
            return;
        }
        var btn = document.getElementById('tfm-submit');
        btn.disabled = true;
        btn.textContent = 'Sending...';

        fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                category: cat,
                text: txt,
                email: email || null,
                page_url: window.location.href
            })
        }).then(function (r) {
            return r.json().then(function (j) { return { ok: r.ok, body: j }; });
        }).then(function (res) {
            if (res.ok && res.body && res.body.ok) {
                showResult(res.body.message || 'Received. Stephen will see this within minutes.', false);
                setTimeout(closeModal, 2200);
            } else {
                var err = (res.body && res.body.detail) || 'Submission failed. Please try again.';
                showResult(err, true);
                btn.disabled = false;
                btn.textContent = 'Send to founder';
            }
        }).catch(function (err) {
            showResult('Network error: ' + err.message, true);
            btn.disabled = false;
            btn.textContent = 'Send to founder';
        });
    }

    function attachTriggers() {
        injectStyle();
        var triggers = document.querySelectorAll('.js-feedback-trigger');
        for (var i = 0; i < triggers.length; i++) {
            triggers[i].addEventListener('click', function (e) {
                e.preventDefault();
                openModal();
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', attachTriggers);
    } else {
        attachTriggers();
    }
})();
