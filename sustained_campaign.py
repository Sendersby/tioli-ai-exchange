"""Sustained autonomous campaign — all agents, all platforms, maximum output."""

import asyncio
import json
import os
import time
import base64
import requests
from datetime import datetime, timezone
from requests_oauthlib import OAuth1


# Platform credentials
TWITTER_AUTH = OAuth1(
    'dpgwSYZ3dRKmUdZdQcbeAdUaG',
    'zUa65tIhsdNQPgB23FB5n4QcO9446keKOy6Mnm7CHsezJALQe7',
    '1225164414-DWUEpoVpIeRay1OlTxQrX36O90fUJsqjuXSdNOZ',
    'O9sXfrwvVqumHclnnO9OkXqL5dnvv40rHxH5biJRFKbqT',
)

DISCORD_WEBHOOK = 'https://discord.com/api/webhooks/1490266467629793343/B2rxSMjw8g3228lIA_ri6rrmcsKDybrLnYoyYyLlBVLLFXbSxs_1flbBNpdMLm9XzaAl'

DEVTO_KEY = 'N9yWNEuurfTZPnbMVsCsYGN6'

GITHUB_TOKEN = 'REDACTED_GITHUB_PAT'
GITHUB_ORG = 'TiOLi-AGENTIS'


def post_tweet(text):
    resp = requests.post('https://api.x.com/2/tweets', json={'text': text}, auth=TWITTER_AUTH)
    if resp.status_code == 201:
        tid = resp.json()['data']['id']
        print(f'  Tweet: https://x.com/Tioli4/status/{tid}')
        return True
    else:
        print(f'  Tweet error: {resp.status_code} {resp.text[:200]}')
        return False


def post_discord(thread_name, content):
    resp = requests.post(DISCORD_WEBHOOK, json={
        'username': 'The Ambassador',
        'thread_name': thread_name,
        'content': content,
    })
    print(f'  Discord: {resp.status_code}')
    return resp.status_code in (200, 204)


def post_devto(title, body, tags):
    resp = requests.post('https://dev.to/api/articles',
        headers={'api-key': DEVTO_KEY, 'Content-Type': 'application/json'},
        json={'article': {'title': title, 'body_markdown': body, 'published': True, 'tags': tags}},
    )
    if resp.status_code == 201:
        url = resp.json().get('url', 'published')
        print(f'  DEV.to: {url}')
        return True
    else:
        print(f'  DEV.to error: {resp.status_code} {resp.text[:200]}')
        return False


def post_github_discussion(title, body):
    headers = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
    # Create as a repo README update or issue
    encoded = base64.b64encode(body.encode()).decode()
    resp = requests.put(
        f'https://api.github.com/repos/{GITHUB_ORG}/.github/contents/content/{int(time.time())}.md',
        headers=headers,
        json={'message': title, 'content': encoded},
    )
    print(f'  GitHub: {resp.status_code}')
    return resp.status_code in (200, 201)


async def generate_content(prompt, client):
    """Use Claude to generate content."""
    response = await client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=1000,
        system=(
            'You are a professional content writer for TiOLi AGENTIS, a governed AI agent exchange. '
            'Write in a tone of technical proficiency and legitimate value. Never use hype. '
            'Never call AGENTIS a marketplace — it is economic infrastructure. '
            'Always include a link to agentisexchange.com. Keep posts concise and compelling.'
        ),
        messages=[{'role': 'user', 'content': prompt}],
    )
    return response.content[0].text


async def run_campaign():
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))

    print('=' * 70)
    print('  SUSTAINED CAMPAIGN — All Platforms, Maximum Output')
    print(f'  {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}')
    print('=' * 70)

    # BATCH 1: Twitter thread — 5 tweets
    print('\n--- TWITTER: 5-tweet thought leadership thread ---')

    tweets = [
        await generate_content(
            'Write a single tweet (max 270 chars) about why AI agents need economic settlement infrastructure. '
            'Pattern break style — start with a surprising statement. Include agentisexchange.com', client),
        await generate_content(
            'Write a single tweet (max 270 chars) about 7 autonomous AI board agents governing a financial exchange. '
            'Technical credibility tone. Include agentisexchange.com/governance', client),
        await generate_content(
            'Write a single tweet (max 270 chars) about the difference between an AI marketplace and governed economic infrastructure. '
            'Include agentisexchange.com', client),
        await generate_content(
            'Write a single tweet (max 270 chars) about binding AI dispute arbitration with published case law. '
            'Include agentisexchange.com', client),
        await generate_content(
            'Write a single tweet (max 270 chars) about registering an AI agent in 30 seconds with escrow protection. '
            'Call to action. Include agentisexchange.com/get-started', client),
    ]

    for i, tweet in enumerate(tweets):
        # Trim to 280 chars
        tweet_text = tweet.strip().replace('"', '').replace("'", '')[:278]
        post_tweet(tweet_text)
        time.sleep(5)

    # BATCH 2: Discord — 3 threads
    print('\n--- DISCORD: 3 thought leadership threads ---')

    disc1 = await generate_content(
        'Write a Discord post (200-300 words) titled "What Governed AI Agent Commerce Actually Means". '
        'Explain the concept in practical terms. Include agentisexchange.com', client)
    post_discord('What Governed AI Agent Commerce Actually Means', disc1[:1900])
    time.sleep(3)

    disc2 = await generate_content(
        'Write a Discord post (200-300 words) titled "How Our 7 AI Board Agents Make Decisions". '
        'Explain the board structure, voting, Prime Directives. Include agentisexchange.com/governance', client)
    post_discord('How Our 7 AI Board Agents Make Decisions', disc2[:1900])
    time.sleep(3)

    disc3 = await generate_content(
        'Write a Discord post (200-300 words) titled "Why We Built Dispute Arbitration for AI Agents". '
        'Explain DAP, binding rulings, case law. Include agentisexchange.com', client)
    post_discord('Why We Built Dispute Arbitration for AI Agents', disc3[:1900])
    time.sleep(3)

    # BATCH 3: DEV.to — 2 technical articles
    print('\n--- DEV.to: 2 technical articles ---')

    art1 = await generate_content(
        'Write a technical article (600-800 words) titled "Building a Constitutional Framework for Autonomous AI Agents". '
        'Cover: Prime Directives, 4-tier code evolution, reserve floor, spending ceiling. '
        'Technical audience. Include code examples or architecture diagrams in markdown. '
        'Include links to agentisexchange.com and agentisexchange.com/governance', client)
    post_devto('Building a Constitutional Framework for Autonomous AI Agents', art1, ['ai', 'architecture', 'governance', 'agents'])
    time.sleep(3)

    art2 = await generate_content(
        'Write a technical article (600-800 words) titled "MCP-Native Agent Discovery: How AI Agents Find Each Other". '
        'Cover: Model Context Protocol, agent registration, capability declaration, reputation scoring. '
        'Developer audience. Include API endpoint examples. '
        'Include links to exchange.tioli.co.za/redoc and agentisexchange.com/get-started', client)
    post_devto('MCP-Native Agent Discovery: How AI Agents Find Each Other', art2, ['ai', 'mcp', 'api', 'developers'])
    time.sleep(3)

    # BATCH 4: GitHub — technical content
    print('\n--- GITHUB: Technical documentation ---')

    readme_update = await generate_content(
        'Write a technical README section (300 words) titled "API Quickstart" showing how to register an agent, '
        'list a service, and check reputation via curl commands against exchange.tioli.co.za. '
        'Include real endpoint paths from the API.', client)
    post_github_discussion('Add API Quickstart guide', f'# API Quickstart\n\n{readme_update}')

    # BATCH 5: Cross-post the DEV.to articles to Discord
    print('\n--- CROSS-POST: DEV.to articles to Discord ---')
    post_discord(
        'New Article: Constitutional Framework for AI Agents',
        f'New technical article published on DEV.to:\n\n'
        f'**Building a Constitutional Framework for Autonomous AI Agents**\n\n'
        f'Covers Prime Directives, 4-tier code evolution, reserve floor, spending ceiling.\n\n'
        f'Read: https://dev.to/sendersby\n\n'
        f'agentisexchange.com/governance'
    )

    # Log everything
    print(f'\n{"=" * 70}')
    print('  CAMPAIGN BATCH COMPLETE')
    print('  Tweets: 5')
    print('  Discord threads: 4')
    print('  DEV.to articles: 2')
    print('  GitHub content: 1')
    print(f'  Total pieces: 12')
    print(f'{"=" * 70}')


if __name__ == '__main__':
    asyncio.run(run_campaign())
