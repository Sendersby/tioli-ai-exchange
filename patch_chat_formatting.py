"""Patch chat_engine.py to format tool results as human-readable text."""

import os

path = "app/boardroom/chat_engine.py"
with open(path) as f:
    content = f.read()

# Find and replace the raw JSON tool result formatting
old = '''        result_text = "\\n\\n".join([
            f"**{tr[\'tool\']}** result:\\n```\\n{json.dumps(tr.get(\'result\', tr.get(\'error\', \'\')), indent=2, default=str)[:800]}\\n```"
            for tr in tool_results
        ])
        text_parts.append(result_text)'''

new = '''        for tr in tool_results:
            data = tr.get("result", tr.get("error", {}))
            tool_name = tr["tool"].replace("_", " ").title()
            if isinstance(data, dict):
                lines = [f"**{tool_name}:**"]
                for k, v in data.items():
                    clean_key = k.replace("_", " ").title()
                    if isinstance(v, dict):
                        for sk, sv in v.items():
                            lines.append(f"  {sk}: {sv}")
                    elif isinstance(v, (int, float)) and "zar" in k.lower():
                        lines.append(f"  {clean_key}: R{v:,.2f}")
                    elif isinstance(v, bool):
                        lines.append(f"  {clean_key}: {'Yes' if v else 'No'}")
                    else:
                        lines.append(f"  {clean_key}: {v}")
                text_parts.append("\\n".join(lines))
            else:
                text_parts.append(f"**{tool_name}:** {str(data)[:500]}")'''

if old in content:
    content = content.replace(old, new)
    with open(path, "w") as f:
        f.write(content)
    print("Tool formatting patched successfully")
else:
    print("Could not find exact match — trying alternate")
    # Try to find the block by key phrase
    if 'result_text = "\\n\\n".join' in content:
        # Find start and end
        start = content.index('result_text = "\\n\\n".join')
        # Find the text_parts.append(result_text) after it
        end = content.index("text_parts.append(result_text)", start) + len("text_parts.append(result_text)")
        old_block = content[start:end]
        content = content.replace(old_block, new.lstrip())
        with open(path, "w") as f:
            f.write(content)
        print("Tool formatting patched (alternate method)")
    else:
        print("WARNING: Could not patch — manual edit needed")
        # Show what's actually in the file around tool results
        for i, line in enumerate(content.split('\n')):
            if 'result_text' in line or 'tool_results' in line:
                print(f"  Line {i}: {line.strip()[:80]}")
