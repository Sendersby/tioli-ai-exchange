/* TiOLi AI Transact Exchange — Client-side JavaScript */

document.addEventListener('DOMContentLoaded', () => {
    // Auto-refresh dashboard stats every 30 seconds
    if (document.querySelector('.dashboard')) {
        setInterval(refreshStats, 30000);
    }
});

async function refreshStats() {
    try {
        const resp = await fetch('/api/stats');
        if (!resp.ok) return;
        const data = await resp.json();

        const values = document.querySelectorAll('.stat-value');
        if (values.length >= 6) {
            values[0].textContent = data.chain_length || '0';
            values[1].textContent = data.total_transactions || '0';
            values[2].textContent = data.agent_count || '0';
            values[3].textContent = parseFloat(data.founder_earnings || 0).toFixed(4);
            values[4].textContent = parseFloat(data.charity_total || 0).toFixed(4);
        }
    } catch (e) {
        // Silent fail — dashboard still works with stale data
    }
}
