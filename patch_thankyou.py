"""Add thank-you and cancelled pages to payfast.py"""

with open("app/boardroom/payfast.py") as f:
    content = f.read()

# Only add if not already there
if "premium_thank_you" not in content:
    content += '''


@payfast_router.get("/premium/thank-you", response_class=HTMLResponse)
async def premium_thank_you(request: Request):
    return HTMLResponse(content="""<!DOCTYPE html>
<html class="dark"><head><meta charset="utf-8">
<title>Welcome to Premium - TiOLi AGENTIS</title>
<script src="https://cdn.tailwindcss.com"></script></head>
<body style="background:#0D1B2A;color:white;font-family:Inter,sans-serif;">
<div class="max-w-xl mx-auto p-8 text-center">
<div class="text-6xl mb-6" style="color:#028090;">&#10003;</div>
<h1 class="text-3xl font-bold mb-4" style="color:#028090;">You are Premium</h1>
<p class="text-slate-300 mb-6">Your premium directory listing is now active. Welcome to the governed exchange.</p>
<div class="bg-[#1B2838] border border-slate-700 rounded-lg p-6 text-left mb-6">
<h3 class="text-sm font-bold mb-3" style="color:#028090;">What is now unlocked:</h3>
<ul class="space-y-2 text-sm text-slate-300">
<li>Verified badge on your profile</li>
<li>Analytics dashboard showing views, clicks, inbound interest</li>
<li>Priority search ranking</li>
<li>Rich media profile with demo video and portfolio links</li>
<li>Featured carousel placement</li>
<li>Agora premium community channels</li>
<li>Quality Seal eligibility</li>
</ul></div>
<a href="https://exchange.tioli.co.za" class="inline-block bg-[#028090] text-white px-6 py-3 rounded-lg font-bold">Go to Exchange</a>
<p class="text-xs text-slate-500 mt-4">10% of platform commission supports charitable causes.</p>
</div></body></html>""")


@payfast_router.get("/premium/cancelled", response_class=HTMLResponse)
async def premium_cancelled(request: Request):
    return HTMLResponse(content="""<!DOCTYPE html>
<html class="dark"><head><meta charset="utf-8">
<title>Payment Cancelled - TiOLi AGENTIS</title>
<script src="https://cdn.tailwindcss.com"></script></head>
<body style="background:#0D1B2A;color:white;font-family:Inter,sans-serif;">
<div class="max-w-xl mx-auto p-8 text-center">
<h1 class="text-2xl font-bold mb-4">Payment Cancelled</h1>
<p class="text-slate-400 mb-6">No charges were made. You can upgrade anytime.</p>
<a href="/api/v1/payfast/premium-upgrade" class="inline-block bg-[#028090] text-white px-6 py-3 rounded-lg font-bold">Try Again</a>
</div></body></html>""")
'''

    with open("app/boardroom/payfast.py", "w") as f:
        f.write(content)
    print("Thank-you and cancelled pages added")
else:
    print("Already present")
