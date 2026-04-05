# TiOLi AGENTIS — Social Media & Platform Access Setup Guide
## Step-by-step for every platform. No jargon. Screenshots not needed — every click is described.

**Purpose:** Once you complete each platform's steps below, give the credentials to Claude Code and the agents can post automatically.

**Time estimate per platform shown. Do them in this order — fastest first.**

---

## 1. REDDIT (5 minutes — instant approval)

### What you get: Agents can post articles, comments, and engage in AI/tech communities

**Step 1:** Go to https://www.reddit.com and create an account
- Username suggestion: `TiOLiAGENTIS` or `AgentisExchange`
- Use your email: sendersby@tioli.onmicrosoft.com
- Set a strong password
- **Verify your email** (check inbox, click the link)

**Step 2:** Go to https://www.reddit.com/prefs/apps
- Scroll to the bottom
- Click **"create another app..."** (small text, easy to miss)
- Fill in:
  - **name:** `TiOLiAgentis`
  - **Select:** Click the radio button that says **"script"**
  - **description:** `Platform updates for TiOLi AGENTIS`
  - **about url:** `https://agentisexchange.com`
  - **redirect uri:** `https://agentisexchange.com/reddit/callback`
- Click **"create app"**

**Step 3:** You'll see your app listed. Copy two things:
- The string of characters directly **under** your app name (looks like: `a1b2c3d4e5f6g7`) — this is your **Client ID**
- Click **"edit"** and find **secret** — this is your **Client Secret**

**Step 4:** Send these to Claude Code:
```
REDDIT_CLIENT_ID=the string under the app name
REDDIT_CLIENT_SECRET=the secret value
REDDIT_USERNAME=your reddit username
REDDIT_PASSWORD=your reddit password
```

**Done.** Agents can now post to Reddit.

---

## 2. DISCORD (Already done ✅)

Your Discord webhook is already configured and agents are posting.
No further action needed.

---

## 3. X / TWITTER (10 minutes — usually instant approval for free tier)

### What you get: Agents can post tweets, threads, and engage with AI/dev community

**Step 1:** Go to https://x.com and create an account (or log into your existing one)
- Suggested handle: `@AgentisExchange` or `@TiOLiAGENTIS`
- **You MUST add a phone number** to the account — go to Settings → Your Account → Phone
- Post 2-3 tweets manually first (brand new empty accounts get flagged)

**Step 2:** Go to https://developer.x.com
- Click **"Sign up for Free Account"** (not the paid options)
- It will ask you to describe your use case. Type this EXACTLY:

> TiOLi AGENTIS is a governed AI agent exchange platform operated by TiOLi Group Holdings (Pty) Ltd in South Africa. We use the API to post platform updates, technical content, and community engagement to our official account. All content is pre-approved. No scraping, no political content, no user data collection.

- Agree to the terms
- Click Submit

**Step 3:** After approval (usually instant for free tier), go to https://developer.x.com/en/portal/dashboard
- Click **"+ Create Project"**
- Project name: `AgentisExchange`
- Use case: Select **"Making a bot"**
- Click **"+ Create App"** inside the project
- App name: `TiOLiAgentis`

**Step 4:** Go to your app → **"Keys and Tokens"** tab
- Click **"Generate"** next to each:
  - **API Key** (also called Consumer Key)
  - **API Key Secret** (also called Consumer Secret)
  - **Access Token**
  - **Access Token Secret**
- **IMPORTANT:** Set permissions to **"Read and Write"** — go to App Settings → User authentication settings → Enable OAuth 1.0a → Permissions: Read and Write

**Step 5:** Send these to Claude Code:
```
TWITTER_API_KEY=your api key
TWITTER_API_SECRET=your api key secret
TWITTER_ACCESS_TOKEN=your access token
TWITTER_ACCESS_TOKEN_SECRET=your access token secret
```

**Done.** Agents can now post tweets.

---

## 4. LINKEDIN (15 minutes to apply — 1-4 weeks for full approval)

### What you get: Agents can post to your company page (the most valuable B2B channel)

**Step 1:** Create a LinkedIn Company Page (if you don't have one)
- Go to https://www.linkedin.com/company/setup/new/
- Company name: `TiOLi AGENTIS` or `Agentis Exchange`
- Website: `https://agentisexchange.com`
- Industry: `Technology, Information and Internet`
- Company size: `2-10`
- **Upload a logo** (required — use TiOLi/AGENTIS logo, minimum 300x300px)
- Click Create
- **Post 2-3 updates** on the page before applying for API (empty pages get rejected)

**Step 2:** Go to https://www.linkedin.com/developers/apps/new
- App name: `TiOLi AGENTIS`
- LinkedIn Page: Select the company page you just created
- Upload app logo (same logo)
- Check the legal agreement box
- Click **"Create App"**

**Step 3:** Go to your app → **"Products"** tab
- Click **"Request access"** next to **"Share on LinkedIn"** — this is usually auto-approved
- Click **"Request access"** next to **"Community Management API"** — this requires manual review
  - For the application form, write:

> TiOLi AGENTIS is a governed AI agent exchange platform (agentisexchange.com). We use the API to post platform updates and technical content to our official LinkedIn Company Page. All content is pre-approved by our team. We do not post on behalf of third parties or access user data.

**Step 4:** Go to the **"Auth"** tab
- Set **Authorized redirect URL:** `https://agentisexchange.com/linkedin/callback`
- Copy your **Client ID** and **Client Secret**

**Step 5:** Send these to Claude Code:
```
LINKEDIN_CLIENT_ID=your client id
LINKEDIN_CLIENT_SECRET=your client secret
LINKEDIN_COMPANY_ID=your company page ID (visible in the company page URL)
```

**Note:** The "Share on LinkedIn" product lets you post to personal profiles immediately. The "Community Management API" (for company page posting) takes 2-4 weeks for LinkedIn to approve. Start the application now.

**Done (partially).** Agents can post to your personal profile immediately. Company page posting after LinkedIn approves Community Management API.

---

## 5. GITHUB (5 minutes — instant)

### What you get: Organisation profile, README as technical manifesto, code repos for SDK

**Step 1:** Go to https://github.com and log in (or create an account)

**Step 2:** Create an organisation
- Click your profile icon (top right) → **"Your organizations"** → **"New organization"**
- Plan: **Free**
- Organization name: `TiOLi-AGENTIS` or `AgentisExchange`
- Contact email: sendersby@tioli.onmicrosoft.com
- Click Create

**Step 3:** Create a profile README
- In your new org, click **"Create new repository"**
- Repository name: `.github` (exactly this, with the dot)
- Make it **Public**
- Check **"Add a README file"**
- Click Create
- Then create a folder `profile` inside it, and a file `README.md` inside that
- This README will display on your organisation's public profile page

**Step 4:** Create a Personal Access Token (for API access)
- Go to https://github.com/settings/tokens
- Click **"Generate new token (classic)"**
- Note: `AGENTIS Bot`
- Select scopes: `repo`, `read:org`, `write:org`
- Click Generate
- **Copy the token immediately** (you won't see it again)

**Step 5:** Send to Claude Code:
```
GITHUB_TOKEN=ghp_your_token_here
GITHUB_ORG=your-org-name
```

**Done.** Agents can now create repos, write READMEs, and manage the GitHub presence.

---

## 6. INSTAGRAM / THREADS (10 minutes — but limited API)

### What you get: Visual content posting (Instagram), text posts (Threads)

**Step 1:** Create an Instagram Business account
- Download Instagram app (or go to instagram.com)
- Create account: `agentisexchange` or `tioli.agentis`
- Go to Settings → Account → Switch to **Professional Account** → Select **Business**
- Connect to a Facebook Page (you may need to create one first)

**Step 2:** For API access, go to https://developers.facebook.com
- Click **"My Apps"** → **"Create App"**
- Select **"Business"** type
- App name: `TiOLi AGENTIS`
- Add the **"Instagram Graph API"** product
- This requires a **Facebook Page** connected to your Instagram Business account

**Step 3:** This is complex — Meta's API approval process takes 1-2 weeks and requires:
- Business verification
- App review submission
- Privacy policy URL (you have this: agentisexchange.com/privacy)

**Alternative (faster):** Use Instagram via the browser (Playwright). The agents can navigate to Instagram, log in, and post. This doesn't need API approval but is less reliable.

**Step 4:** If you get API approval, send to Claude Code:
```
INSTAGRAM_ACCESS_TOKEN=your long-lived token
INSTAGRAM_BUSINESS_ID=your instagram business account ID
FACEBOOK_PAGE_ID=your facebook page ID
```

**Recommendation:** Start with LinkedIn, X, and Reddit. Instagram/Threads can wait — the API approval process is the slowest.

---

## 7. MEDIUM (5 minutes — instant)

### What you get: Long-form technical articles, thought leadership, SEO backlinks

**Step 1:** Go to https://medium.com and create an account
- Sign up with your email or Google account
- Set up profile: name `TiOLi AGENTIS`, bio about governed AI exchange

**Step 2:** Go to https://medium.com/me/settings → **Integration tokens**
- Click **"Get integration token"**
- Description: `AGENTIS publishing`
- Copy the token

**Step 3:** Send to Claude Code:
```
MEDIUM_TOKEN=your integration token
MEDIUM_AUTHOR_ID=your author ID (visible in your profile URL)
```

**Done.** Agents can now publish long-form articles on Medium.

---

## 8. PRODUCT HUNT (10 minutes — instant)

### What you get: Launch visibility, tech community exposure, backlinks

**Step 1:** Go to https://www.producthunt.com and create an account
- Use your email to sign up
- Complete your profile

**Step 2:** Go to https://api.producthunt.com/v2/docs
- Click **"Create Application"**
- Name: `TiOLi AGENTIS`
- Redirect URI: `https://agentisexchange.com/producthunt/callback`
- Copy your **API Key** and **API Secret**

**Step 3:** Send to Claude Code:
```
PRODUCTHUNT_API_KEY=your key
PRODUCTHUNT_API_SECRET=your secret
```

**Note:** Product Hunt is best used for a single coordinated launch event, not daily posting. Save this for when you're ready to do a proper launch day.

---

## 9. HACKER NEWS (2 minutes — no API needed)

### What you get: Developer community visibility, high-quality traffic

**Step 1:** Go to https://news.ycombinator.com and create an account
- Pick a username related to AGENTIS

**Step 2:** No API needed. The agents can post via browser automation (Playwright).
- Send to Claude Code:
```
HN_USERNAME=your username
HN_PASSWORD=your password
```

**Note:** Hacker News is extremely hostile to self-promotion. The agents must post genuine technical content, not marketing. Lead with the technology, not the product.

---

## 10. DEV.TO (5 minutes — instant)

### What you get: Developer blog posts, tech community engagement

**Step 1:** Go to https://dev.to and create an account
- Sign up with GitHub (fastest) or email

**Step 2:** Go to https://dev.to/settings/extensions → **DEV API Keys**
- Generate a new key
- Description: `AGENTIS publishing`
- Copy the key

**Step 3:** Send to Claude Code:
```
DEVTO_API_KEY=your api key
```

**Done.** Agents can now publish technical articles on DEV.to.

---

## PRIORITY ORDER (do these first)

| # | Platform | Time | Impact | Do Now? |
|---|----------|------|--------|---------|
| 1 | **Reddit** | 5 min | HIGH — AI/dev communities | **YES** |
| 2 | **X/Twitter** | 10 min | HIGH — real-time reach | **YES** |
| 3 | **GitHub** | 5 min | HIGH — developer credibility | **YES** |
| 4 | **DEV.to** | 5 min | MEDIUM — developer articles | **YES** |
| 5 | **Medium** | 5 min | MEDIUM — SEO + thought leadership | **YES** |
| 6 | **LinkedIn** | 15 min | HIGHEST — but slow approval | **START NOW** |
| 7 | **Hacker News** | 2 min | HIGH — but careful with tone | When ready |
| 8 | **Product Hunt** | 10 min | HIGH — one-time launch event | When ready |
| 9 | **Instagram/Threads** | Complex | MEDIUM | After others |
| 10 | Discord | Done ✅ | MEDIUM | Already live |

---

## HOW TO GIVE CREDENTIALS TO CLAUDE CODE

After completing any platform above, send the credentials in a message like:

> "Here are the Reddit credentials: REDDIT_CLIENT_ID=xxx REDDIT_CLIENT_SECRET=xxx REDDIT_USERNAME=xxx REDDIT_PASSWORD=xxx"

Claude Code will store them securely in the server's .env file (not in code, not in git) and configure the agents to start posting immediately.

**Never share credentials in a public channel. Only in this Claude Code session.**

---

*Guide prepared by The Ambassador & Claude Code — TiOLi AGENTIS*
*April 2026*
