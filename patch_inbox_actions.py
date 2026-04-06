"""Add Acknowledge + Reply + Dismiss to inbox items."""

with open("app/templates/boardroom/inbox.html") as f:
    c = f.read()

# Replace the action buttons section
old_actions = """            {% if item.action_type == 'APPROVAL' %}
            <form method="post" action="/boardroom/inbox/{{ item.id }}/approve">
              <button class="text-xs font-bold px-3 py-1.5 rounded-md bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 border border-emerald-500/30 transition-all">Approve</button>
            </form>
            <form method="post" action="/boardroom/inbox/{{ item.id }}/reject">
              <button class="text-xs font-bold px-3 py-1.5 rounded-md bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30 transition-all">Reject</button>
            </form>
            {% else %}
            <form method="post" action="/boardroom/inbox/{{ item.id }}/acknowledge">
              <button class="text-xs font-bold px-3 py-1.5 rounded-md bg-[#028090]/20 text-[#77d4e5] hover:bg-[#028090]/30 border border-[#028090]/30 transition-all">Acknowledge</button>
            </form>
            {% endif %}"""

new_actions = """            <div class="flex flex-col gap-1.5">
              {% if item.action_type == 'APPROVAL' %}
              <button onclick="inboxAction(this, '{{ item.id }}', 'APPROVE')" class="text-xs font-bold px-3 py-1.5 rounded-md bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 border border-emerald-500/30 transition-all w-full">Approve</button>
              <button onclick="inboxAction(this, '{{ item.id }}', 'REJECT')" class="text-xs font-bold px-3 py-1.5 rounded-md bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30 transition-all w-full">Reject</button>
              {% else %}
              <button onclick="inboxAction(this, '{{ item.id }}', 'ACKNOWLEDGE')" class="text-xs font-bold px-3 py-1.5 rounded-md bg-[#028090]/20 text-[#77d4e5] hover:bg-[#028090]/30 border border-[#028090]/30 transition-all w-full">Acknowledge</button>
              {% endif %}
              <button onclick="showReplyField('{{ item.id }}')" class="text-xs font-bold px-3 py-1.5 rounded-md bg-[#D4A94A]/10 text-[#D4A94A] hover:bg-[#D4A94A]/20 border border-[#D4A94A]/30 transition-all w-full">Reply</button>
              <button onclick="inboxAction(this, '{{ item.id }}', 'DISMISS')" class="text-xs px-3 py-1 rounded-md text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-all w-full">Dismiss</button>
            </div>"""

c = c.replace(old_actions, new_actions)

# Add reply field after the action buttons div (inside the card)
old_card_close = """        </div>
      </div>
      {% endfor %}"""

new_card_close = """        </div>
        <div id="reply-{{ item.id }}" class="hidden mt-3 border-t border-slate-700/30 pt-3">
          <textarea id="reply-text-{{ item.id }}" placeholder="Type your reply to the agent..." rows="2" class="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:border-[#D4A94A] focus:outline-none"></textarea>
          <button onclick="sendInboxReply('{{ item.id }}', '{{ item.agent }}')" class="mt-1.5 text-xs font-bold px-4 py-1.5 rounded-md bg-[#D4A94A] text-[#0D1B2A] hover:bg-[#edc05f] transition-all">Send Reply to {{ item.agent|title }}</button>
        </div>
      </div>
      {% endfor %}"""

c = c.replace(old_card_close, new_card_close)

# Add card ID and agent data attribute
c = c.replace(
    '<div class="bg-[#1B2838] border rounded-lg p-4 transition-all',
    '<div id="item-{{ item.id }}" data-agent="{{ item.agent }}" class="bg-[#1B2838] border rounded-lg p-4 transition-all'
)

# Add JavaScript before endblock
js_code = """
<script>
async function inboxAction(btn, itemId, action) {
  const resp = await fetch('/api/v1/boardroom/inbox/' + itemId + '/action', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action: action, response: action})
  });
  if (resp.ok) {
    var labels = {DISMISS: 'Dismissed', ACKNOWLEDGE: 'Acknowledged', APPROVE: 'Approved', REJECT: 'Rejected'};
    var colors = {DISMISS: 'text-slate-500', ACKNOWLEDGE: 'text-[#028090]', APPROVE: 'text-emerald-400', REJECT: 'text-red-400'};
    btn.parentElement.innerHTML = '<span class="text-xs font-bold ' + (colors[action]||'') + '">' + (labels[action]||action) + '</span>';
    if (action === 'DISMISS') document.getElementById('item-' + itemId).style.opacity = '0.3';
  }
}

function showReplyField(itemId) {
  var el = document.getElementById('reply-' + itemId);
  el.classList.toggle('hidden');
  if (!el.classList.contains('hidden')) document.getElementById('reply-text-' + itemId).focus();
}

async function sendInboxReply(itemId, agent) {
  var text = document.getElementById('reply-text-' + itemId).value.trim();
  if (!text) return;
  // Mark as replied in inbox
  await fetch('/api/v1/boardroom/inbox/' + itemId + '/action', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action: 'REPLY', response: text})
  });
  // Also send to agent's chat so they see it
  if (agent && agent !== 'Board') {
    await fetch('/api/v1/boardroom/agents/' + agent + '/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: 'Founder reply to your inbox request: ' + text})
    });
  }
  document.getElementById('reply-' + itemId).innerHTML = '<div class="text-xs text-[#D4A94A] py-2">Reply sent: ' + text.substring(0, 80) + '</div>';
}
</script>
"""

if 'function inboxAction' not in c:
    c = c.replace('{% endblock %}', js_code + '{% endblock %}')

with open("app/templates/boardroom/inbox.html", "w") as f:
    f.write(c)
print("Inbox updated: Acknowledge + Reply + Dismiss")
