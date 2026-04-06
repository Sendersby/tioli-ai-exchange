"""Fix inbox template — make items show full content, expandable on click."""

with open("app/templates/boardroom/inbox.html") as f:
    c = f.read()

old_body = '<div class="text-xs text-slate-400 mb-1">{{ item.body }}</div>'
new_body = (
    '<div class="text-xs text-slate-400 mb-1">'
    '<div id="body-{{ item.id }}" style="max-height:40px;overflow:hidden;cursor:pointer" '
    'onclick="var el=document.getElementById(\'body-{{ item.id }}\');'
    'if(el.style.maxHeight===\'40px\'){el.style.maxHeight=\'none\'}else{el.style.maxHeight=\'40px\'}">'
    '{{ item.body }}'
    '</div>'
    '<span class="text-[10px] text-[#77d4e5] cursor-pointer" '
    'onclick="var el=document.getElementById(\'body-{{ item.id }}\');'
    'if(el.style.maxHeight===\'40px\'){el.style.maxHeight=\'none\';this.textContent=\'Click to collapse\'}else{el.style.maxHeight=\'40px\';this.textContent=\'Click to expand\'}">'
    'Click to expand</span>'
    '</div>'
)

c = c.replace(old_body, new_body)

with open("app/templates/boardroom/inbox.html", "w") as f:
    f.write(c)
print("Inbox template fixed — body expandable on click")
