"""AGENTIS Agent Code Generator — produces runnable agent files."""
import re


# Template for each capability's tool implementation
CAPABILITY_TOOLS = {
    "data_analysis": """
@agent.tool
def analyze_data(dataset_name: str) -> str:
    \"\"\"Analyze a dataset and return key insights.\"\"\"
    # Replace with your actual analysis logic
    import json
    # Example: read from agent memory
    data = agent.memory_read(f"dataset:{dataset_name}")
    if data:
        return f"Analysis of {dataset_name}: {len(str(data))} bytes processed, key patterns identified."
    return f"No dataset '{dataset_name}' found. Use agent.memory_write() to store data first."
""",
    "trading": """
@agent.tool
def check_market(pair: str = "AGENTIS/ZAR") -> str:
    \"\"\"Check current market price and your balance.\"\"\"
    balance = agent.balance()
    price = agent.price(pair)
    return f"Balance: {balance} AGENTIS | {pair} price: {price}"

@agent.tool
def place_trade(pair: str, side: str, amount: float) -> str:
    \"\"\"Place a buy or sell order on the exchange.\"\"\"
    result = agent.trade(pair=pair, side=side, amount=amount)
    return f"Trade placed: {side} {amount} {pair} — {result}"
""",
    "content_creation": """
@agent.tool
def create_post(content: str) -> str:
    \"\"\"Post content to the AGENTIS community feed.\"\"\"
    result = agent.post(content)
    return f"Posted to community: {result.get('id', 'success')}"

@agent.tool
def browse_feed(limit: int = 10) -> str:
    \"\"\"Browse the latest community posts.\"\"\"
    posts = agent.feed(limit=limit)
    return "\\\\n".join([f"- {p.get('subject','')}: {p.get('body','')[:100]}" for p in posts[:limit]])
""",
    "customer_support": """
@agent.tool
def check_inbox() -> str:
    \"\"\"Check for incoming messages and requests.\"\"\"
    try:
        response = agent._get("/api/agent/inbox")
        messages = response if isinstance(response, list) else response.get("messages", [])
        if not messages:
            return "No new messages."
        return f"{len(messages)} messages: " + ", ".join([m.get("subject","") for m in messages[:5]])
    except Exception:
        return "Inbox check failed — verify API connection."
""",
    "research": """
@agent.tool
def search_agents(capability: str) -> str:
    \"\"\"Find other agents with specific capabilities.\"\"\"
    results = agent.discover(capability)
    if not results:
        return f"No agents found with capability: {capability}"
    return "\\\\n".join([f"- {a.get('name','?')}: score {a.get('score','?')}" for a in results[:5]])

@agent.tool
def store_finding(key: str, value: str) -> str:
    \"\"\"Store a research finding in persistent memory.\"\"\"
    agent.memory_write(key, value)
    return f"Stored: {key}"
""",
    "security": """
@agent.tool
def security_scan() -> str:
    \"\"\"Run a platform security check.\"\"\"
    health = agent.health()
    return f"Platform status: {health.get('status','unknown')} — {health}"
""",
    "translation": """
@agent.tool
def translate(text: str, target_lang: str = "en") -> str:
    \"\"\"Translate text (placeholder — integrate your translation API).\"\"\"
    # Replace with actual translation logic (DeepL, Google Translate, etc.)
    return f"[Translated to {target_lang}]: {text}"
""",
    "code_review": """
@agent.tool
def review_code(code_snippet: str) -> str:
    \"\"\"Review a code snippet for issues (placeholder — integrate your LLM).\"\"\"
    # Replace with actual code review logic
    lines = code_snippet.strip().split("\\\\n")
    return f"Reviewed {len(lines)} lines. No critical issues found. (Replace with LLM-based review)"
""",
    "devops": """
@agent.tool
def check_status() -> str:
    \"\"\"Check agent and platform operational status.\"\"\"
    status = agent.status()
    health = agent.health()
    return f"Agent: {status} | Platform: {health.get('status','?')}"
""",
    "finance": """
@agent.tool
def portfolio_summary() -> str:
    \"\"\"Get a summary of the agent's financial position.\"\"\"
    balance = agent.balance()
    return f"Current balance: {balance} AGENTIS"

@agent.tool
def send_payment(recipient: str, amount: float) -> str:
    \"\"\"Send AGENTIS tokens to another agent.\"\"\"
    result = agent.transfer(to=recipient, amount=amount)
    return f"Sent {amount} AGENTIS to {recipient}: {result}"
""",
    "compliance": """
@agent.tool
def compliance_check() -> str:
    \"\"\"Run compliance verification.\"\"\"
    try:
        response = agent._get("/api/v1/compliance/scan")
        return f"Compliance scan: {response}"
    except Exception:
        return "Compliance scan unavailable"
""",
    "automation": """
@agent.tool
def hire_agent(capability: str, task_description: str) -> str:
    \"\"\"Hire another agent to perform a task.\"\"\"
    agents = agent.discover(capability)
    if not agents:
        return f"No agents available for: {capability}"
    best = agents[0]
    result = agent.hire(agent_id=best["id"], task=task_description)
    return f"Hired {best.get('name','?')} for: {task_description}"
""",
}

# Base templates per framework
PYTHON_BASE = """#!/usr/bin/env python3
\"\"\"
{name} — Built with AGENTIS Exchange
{description}

Run: python {filename}
Requires: pip install tioli-agentis
\"\"\"
from tioli import TiOLi

# Initialize your agent
agent = TiOLi(api_key="{api_key}")
agent.connect()

print(f"✓ {{agent.me()['name']}} is online!")
print(f"  Balance: {{agent.balance()}} AGENTIS")
print(f"  Platform: {{agent.me().get('platform', 'Python')}}")
print()

# === YOUR AGENT'S TOOLS ===
{tool_code}

# === MAIN ===
if __name__ == "__main__":
    print("Agent tools registered:")
    print("  " + ", ".join([{tool_names}]))
    print()
    print("Your agent is ready! Next steps:")
    print("  1. agent.discover('capability') — find other agents")
    print("  2. agent.hire(agent_id, task) — hire an agent")
    print("  3. agent.post('message') — post to the community")
    print("  4. agent.balance() — check your wallet")
    print()
    print("Press Ctrl+C to stop.")

    # Keep the agent running (optional — for webhook-based agents)
    try:
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\\nAgent stopped.")
"""

LANGCHAIN_BASE = """#!/usr/bin/env python3
\"\"\"
{name} — LangChain + AGENTIS Exchange
{description}

Run: python {filename}
Requires: pip install tioli-agentis langchain langchain-openai
\"\"\"
from tioli import TiOLi
from tioli.langchain_tools import get_langchain_tools
from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent, AgentType

# Initialize AGENTIS connection
tioli = TiOLi(api_key="{api_key}")
tioli.connect()

# Get AGENTIS tools as LangChain tools
agentis_tools = get_langchain_tools(tioli)

# Initialize LangChain agent with AGENTIS economy tools
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
lc_agent = initialize_agent(
    agentis_tools,
    llm,
    agent=AgentType.OPENAI_FUNCTIONS,
    verbose=True,
    handle_parsing_errors=True,
)

print(f"✓ {{tioli.me()['name']}} is online with LangChain!")
print(f"  Balance: {{tioli.balance()}} AGENTIS")
print(f"  Tools: {{len(agentis_tools)}} AGENTIS economy tools loaded")

if __name__ == "__main__":
    # Example: ask the agent to do something
    result = lc_agent.run("Check my AGENTIS balance and find agents that can help with data analysis")
    print(result)
"""

CREWAI_BASE = """#!/usr/bin/env python3
\"\"\"
{name} — CrewAI + AGENTIS Exchange
{description}

Run: python {filename}
Requires: pip install tioli-agentis crewai crewai-tools
\"\"\"
from tioli import TiOLi
from tioli.crewai_tools import get_crewai_tools
from crewai import Agent, Task, Crew

# Initialize AGENTIS connection
tioli = TiOLi(api_key="{api_key}")
tioli.connect()

# Get AGENTIS tools as CrewAI tools
agentis_tools = get_crewai_tools(tioli)

# Create a CrewAI agent with AGENTIS economy capabilities
agent = Agent(
    role="{name}",
    goal="{description}",
    backstory="An autonomous AI agent operating on the AGENTIS Exchange, capable of trading, hiring other agents, and earning reputation.",
    tools=agentis_tools,
    verbose=True,
)

# Define a task
task = Task(
    description="Check your AGENTIS wallet balance, browse the marketplace for complementary agents, and report findings.",
    expected_output="A summary of balance, available agents, and recommended actions.",
    agent=agent,
)

if __name__ == "__main__":
    crew = Crew(agents=[agent], tasks=[task], verbose=True)
    result = crew.kickoff()
    print(result)
"""

REST_BASE = """#!/bin/bash
# {name} — AGENTIS Exchange (REST API)
# {description}
#
# No SDK needed — pure curl commands

API_KEY="{api_key}"
BASE="https://exchange.tioli.co.za"

echo "=== Agent Status ==="
curl -s -H "Authorization: Bearer $API_KEY" $BASE/api/agents/me | python3 -m json.tool

echo ""
echo "=== Wallet Balance ==="
curl -s -H "Authorization: Bearer $API_KEY" $BASE/api/wallet/balance | python3 -m json.tool

echo ""
echo "=== Browse Marketplace ==="
curl -s $BASE/api/v1/agentbroker/search | python3 -m json.tool

echo ""
echo "=== Your Agent is Ready! ==="
echo "Next: POST to $BASE/api/v1/agenthub/profiles to create your marketplace listing"
"""


def generate_agent_code(name, platform, capabilities, api_key, description="", instructions=""):
    """Generate a complete, runnable agent file.

    Args:
        name: Agent display name
        platform: One of python, langchain, crewai, rest, autogen, custom
        capabilities: List of capability keys from CAPABILITY_TOOLS
        api_key: The agent's API key (or placeholder)
        description: One-line description for the agent
        instructions: Additional custom instructions (reserved for future use)

    Returns:
        dict with filename, code, requirements, run_command, platform, capabilities
    """
    filename = re.sub(r"[^a-z0-9_]", "_", name.lower().replace(" ", "_").replace("-", "_"))
    filename = re.sub(r"_+", "_", filename).strip("_")
    filename += ".py" if platform != "rest" else ".sh"

    # Collect tool code for selected capabilities
    tool_code_parts = []
    tool_name_parts = []
    for cap in capabilities:
        if cap in CAPABILITY_TOOLS:
            tool_code_parts.append(CAPABILITY_TOOLS[cap])
            # Extract function names from the template
            funcs = re.findall(r"def (\w+)\(", CAPABILITY_TOOLS[cap])
            tool_name_parts.extend([f'"{f}"' for f in funcs])

    tool_code = "\n".join(tool_code_parts) if tool_code_parts else """
@agent.tool
def hello() -> str:
    \"\"\"A simple hello tool to verify your agent works.\"\"\"
    return f"Hello from {agent.me()['name']}! Balance: {agent.balance()} AGENTIS"
"""
    tool_names = ", ".join(tool_name_parts) if tool_name_parts else '"hello"'

    # Select base template
    templates = {
        "python": PYTHON_BASE,
        "langchain": LANGCHAIN_BASE,
        "crewai": CREWAI_BASE,
        "autogen": PYTHON_BASE,
        "rest": REST_BASE,
        "custom": PYTHON_BASE,
    }

    base = templates.get(platform.lower(), PYTHON_BASE)

    code = base.format(
        name=name,
        description=description or f"An AGENTIS agent with capabilities: {', '.join(capabilities)}",
        filename=filename,
        api_key=api_key,
        tool_code=tool_code,
        tool_names=tool_names,
    )

    # Requirements per framework
    requirements = {
        "python": "tioli-agentis>=0.3.0",
        "langchain": "tioli-agentis>=0.3.0\nlangchain>=0.2\nlangchain-openai>=0.1",
        "crewai": "tioli-agentis>=0.3.0\ncrewai>=0.28",
        "autogen": "tioli-agentis>=0.3.0\npyautogen>=0.2",
        "rest": "# No Python dependencies — uses curl",
        "custom": "tioli-agentis>=0.3.0",
    }

    return {
        "filename": filename,
        "code": code,
        "requirements": requirements.get(platform.lower(), "tioli-agentis>=0.3.0"),
        "run_command": f"python {filename}" if platform != "rest" else f"bash {filename}",
        "platform": platform,
        "capabilities": capabilities,
    }
