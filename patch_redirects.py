"""Add /premium/thank-you and /premium/cancelled redirects to main.py"""

with open("app/main.py") as f:
    content = f.read()

if "premium/thank-you" not in content:
    content += '''

# Premium payment return page redirects
from fastapi.responses import RedirectResponse as _PremiumRedirect

@app.get("/premium/thank-you")
async def _premium_thanks():
    return _PremiumRedirect("/api/v1/payfast/premium/thank-you")

@app.get("/premium/cancelled")
async def _premium_cancel():
    return _PremiumRedirect("/api/v1/payfast/premium/cancelled")
'''
    with open("app/main.py", "w") as f:
        f.write(content)
    print("Redirects added to main.py")
else:
    print("Already present")
