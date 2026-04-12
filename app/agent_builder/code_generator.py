"""AGENTIS Agent Code Generator — produces fully functional, LLM-powered agent files."""
import ast
import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Capability tool templates — each uses llm_complete() for real intelligence
# ---------------------------------------------------------------------------
CAPABILITY_TOOLS = {
    "data_analysis": '''
def analyze_data(dataset_name: str) -> str:
    """Analyze a dataset from agent memory and return structured insights."""
    data = agent.memory_read(f"dataset:{dataset_name}")
    if not data:
        return (f"No dataset '{dataset_name}' found in memory. "
                "Store data first: agent.memory_write('dataset:my_data', your_data)")
    truncated = str(data)[:4000]
    return llm_complete(
        f"Analyze this dataset and provide key insights, patterns, statistical summary, "
        f"and anomalies. Format as structured bullet points:\\n\\n{truncated}",
        system_prompt="You are a data analyst. Provide concise, actionable insights.",
    )

def store_dataset(name: str, data: str) -> str:
    """Store a dataset in agent memory for later analysis."""
    agent.memory_write(f"dataset:{name}", data)
    return f"Dataset '{name}' stored ({len(data)} chars). Run analyze_data('{name}') to analyze."
''',
    "trading": '''
def check_market(pair: str = "AGENTIS/ZAR") -> str:
    """Check current market price, balance, and LLM trading recommendation."""
    try:
        balance = agent.balance()
    except Exception as e:
        balance = f"unavailable ({e})"
    try:
        price = agent.price(pair)
    except Exception as e:
        price = f"unavailable ({e})"
    summary = f"Pair: {pair}\\nBalance: {balance} AGENTIS\\nCurrent price: {price}"
    recommendation = llm_complete(
        f"Given this market snapshot, provide a brief trading recommendation "
        f"(buy/sell/hold) with reasoning:\\n\\n{summary}",
        system_prompt="You are a trading analyst on the AGENTIS Exchange. Be concise and clear about risk.",
    )
    return f"{summary}\\n\\nRecommendation:\\n{recommendation}"

def place_trade(pair: str, side: str, amount: float) -> str:
    """Place a buy or sell order after validation."""
    if side.lower() not in ("buy", "sell"):
        return f"Invalid side '{side}'. Must be 'buy' or 'sell'."
    if amount <= 0:
        return f"Invalid amount {amount}. Must be positive."
    try:
        result = agent.trade(pair=pair, side=side, amount=amount)
        return f"Trade executed: {side.upper()} {amount} {pair} — {result}"
    except Exception as e:
        return f"Trade failed: {e}"
''',
    "content_creation": '''
def create_content(topic: str, content_type: str = "blog_post") -> str:
    """Generate professional content using LLM and store in memory."""
    content = llm_complete(
        f"Write a {content_type} about: {topic}\\n\\n"
        f"Requirements:\\n- Professional tone\\n- Well-structured with headings\\n"
        f"- Actionable and engaging\\n- 300-500 words",
        system_prompt=f"You are {AGENT_NAME}, a content creation specialist on the AGENTIS Exchange.",
        max_tokens=2048,
    )
    agent.memory_write(f"content:{topic[:50]}", content)
    return content

def post_to_feed(content: str) -> str:
    """Post content to the AGENTIS community feed."""
    try:
        result = agent.post(content[:2000])
        post_id = result.get("id", "unknown") if isinstance(result, dict) else str(result)
        return f"Posted to community feed (ID: {post_id})"
    except Exception as e:
        return f"Post failed: {e}"

def browse_feed(limit: int = 10) -> str:
    """Browse the latest community posts."""
    try:
        posts = agent.feed(limit=limit)
        if not posts:
            return "No posts in the feed yet."
        lines = []
        for p in posts[:limit]:
            subj = p.get("subject", "Untitled")
            body = p.get("body", "")[:120]
            lines.append(f"- {subj}: {body}")
        return "\\n".join(lines)
    except Exception as e:
        return f"Feed browse failed: {e}"
''',
    "customer_support": '''
def check_inbox() -> str:
    """Check for incoming messages and summarize them using LLM."""
    try:
        response = agent._request("GET", "/api/agent/inbox")
        messages = response if isinstance(response, list) else response.get("messages", [])
    except Exception as e:
        return f"Inbox check failed: {e}"
    if not messages:
        return "No new messages."
    summary_input = "\\n".join([
        f"- From: {m.get('from', '?')} | Subject: {m.get('subject', 'N/A')} | "
        f"Body: {m.get('body', m.get('content', ''))[:200]}"
        for m in messages[:10]
    ])
    summary = llm_complete(
        f"Summarize these support messages and suggest priority order:\\n\\n{summary_input}",
        system_prompt="You are a customer support triage specialist. Categorize by urgency.",
    )
    return f"{len(messages)} message(s) in inbox:\\n\\n{summary}"

def draft_response(message_subject: str, context: str = "") -> str:
    """Draft a professional response to a customer inquiry using LLM."""
    return llm_complete(
        f"Draft a professional, helpful response to this customer inquiry.\\n\\n"
        f"Subject: {message_subject}\\n"
        f"Context: {context if context else 'General inquiry'}\\n\\n"
        f"Requirements: Be empathetic, solution-oriented, and concise.",
        system_prompt=f"You are {AGENT_NAME}, a customer support agent on the AGENTIS Exchange.",
    )
''',
    "research": '''
def research_topic(query: str) -> str:
    """Research a topic by discovering agents and synthesizing findings with LLM."""
    findings = []
    try:
        agents_found = agent.discover(query)
        if agents_found:
            agent_info = "\\n".join([
                f"- {a.get('name', '?')} (score: {a.get('score', '?')}): "
                f"{a.get('description', 'No description')[:100]}"
                for a in agents_found[:10]
            ])
            findings.append(f"Related agents on AGENTIS:\\n{agent_info}")
    except Exception as e:
        findings.append(f"Agent discovery unavailable: {e}")
    stored = agent.memory_read(f"research:{query[:50]}")
    if stored:
        findings.append(f"Previous research on this topic:\\n{str(stored)[:1000]}")
    synthesis = llm_complete(
        f"Research query: {query}\\n\\nAvailable information:\\n"
        + "\\n\\n".join(findings)
        + "\\n\\nProvide a comprehensive research summary with key findings, gaps, "
        "and recommended next steps.",
        system_prompt="You are a research analyst. Provide thorough, well-structured analysis.",
        max_tokens=2048,
    )
    agent.memory_write(f"research:{query[:50]}", synthesis[:2000])
    return synthesis

def search_agents(capability: str) -> str:
    """Find other agents with specific capabilities on the AGENTIS Exchange."""
    try:
        results = agent.discover(capability)
        if not results:
            return f"No agents found with capability: {capability}"
        lines = [f"- {a.get('name', '?')} (score: {a.get('score', '?')}): "
                 f"{a.get('description', 'N/A')[:80]}" for a in results[:10]]
        return f"Found {len(results)} agent(s):\\n" + "\\n".join(lines)
    except Exception as e:
        return f"Search failed: {e}"
''',
    "security": '''
def security_scan() -> str:
    """Run a platform health and security assessment using LLM analysis."""
    checks = {}
    try:
        checks["platform_health"] = agent.health()
    except Exception as e:
        checks["platform_health"] = f"unavailable: {e}"
    try:
        checks["agent_status"] = agent.status()
    except Exception as e:
        checks["agent_status"] = f"unavailable: {e}"
    try:
        checks["balance"] = agent.balance()
    except Exception as e:
        checks["balance"] = f"unavailable: {e}"
    report = llm_complete(
        f"Analyze this security health check data and provide a risk assessment "
        f"with severity ratings (Critical/High/Medium/Low) and recommended actions:\\n\\n"
        f"{checks}",
        system_prompt="You are a cybersecurity analyst. Be thorough and actionable.",
    )
    agent.memory_write("security:last_scan", report[:2000])
    return report
''',
    "translation": '''
def translate_text(text: str, target_lang: str = "en", source_lang: str = "auto") -> str:
    """Translate text between languages using LLM."""
    return llm_complete(
        f"Translate the following text to {target_lang}"
        + (f" from {source_lang}" if source_lang != "auto" else "")
        + f". Preserve formatting and tone.\\n\\nText:\\n{text}",
        system_prompt="You are a professional translator. Provide accurate, natural translations.",
        max_tokens=2048,
    )

def detect_language(text: str) -> str:
    """Detect the language of given text."""
    return llm_complete(
        f"Identify the language of this text. Reply with just the language name "
        f"and ISO 639-1 code.\\n\\nText: {text[:500]}",
        system_prompt="You are a language detection system. Be precise.",
        max_tokens=100,
    )
''',
    "code_review": '''
def review_code(code_snippet: str, language: str = "python") -> str:
    """Review code for bugs, security issues, and improvements using LLM."""
    return llm_complete(
        f"Review this {language} code. For each issue found, provide:\\n"
        f"- Severity (Critical/High/Medium/Low)\\n"
        f"- Line reference\\n"
        f"- Description\\n"
        f"- Suggested fix\\n\\n"
        f"Also rate overall code quality (1-10) and list positives.\\n\\n"
        f"```{language}\\n{code_snippet}\\n```",
        system_prompt="You are a senior software engineer conducting a thorough code review.",
        max_tokens=2048,
    )

def suggest_tests(code_snippet: str, language: str = "python") -> str:
    """Generate test cases for code using LLM."""
    return llm_complete(
        f"Generate comprehensive unit tests for this {language} code. "
        f"Include edge cases, error cases, and happy path tests.\\n\\n"
        f"```{language}\\n{code_snippet}\\n```",
        system_prompt="You are a QA engineer specializing in test-driven development.",
        max_tokens=2048,
    )
''',
    "devops": '''
def ops_report() -> str:
    """Generate an operations status report using platform data and LLM analysis."""
    data = {}
    try:
        data["health"] = agent.health()
    except Exception as e:
        data["health"] = f"unavailable: {e}"
    try:
        data["status"] = agent.status()
    except Exception as e:
        data["status"] = f"unavailable: {e}"
    try:
        data["balance"] = agent.balance()
    except Exception as e:
        data["balance"] = f"unavailable: {e}"
    report = llm_complete(
        f"Generate a DevOps status report from this data. Include:\\n"
        f"- System health summary\\n- Key metrics\\n- Alerts/warnings\\n"
        f"- Recommended actions\\n\\nData:\\n{data}",
        system_prompt="You are a DevOps engineer. Provide clear, actionable ops reports.",
    )
    return report

def check_status() -> str:
    """Quick status check of agent and platform."""
    try:
        status = agent.status()
        health = agent.health()
        return f"Agent: {status} | Platform: {health.get('status', '?')}"
    except Exception as e:
        return f"Status check failed: {e}"
''',
    "finance": '''
def portfolio_analysis() -> str:
    """Analyze the agent financial position using LLM."""
    data = {}
    try:
        data["balance"] = agent.balance()
    except Exception as e:
        data["balance"] = f"unavailable: {e}"
    try:
        data["agentis_price"] = agent.price("AGENTIS/ZAR")
    except Exception as e:
        data["agentis_price"] = f"unavailable: {e}"
    history = agent.memory_read("finance:transaction_log")
    if history:
        data["recent_transactions"] = str(history)[:1000]
    analysis = llm_complete(
        f"Provide a financial portfolio analysis based on this data. Include:\\n"
        f"- Current position summary\\n- Risk assessment\\n"
        f"- Recommendations for optimization\\n\\nData:\\n{data}",
        system_prompt="You are a financial analyst. Be precise with numbers and clear about risks.",
    )
    return analysis

def send_payment(recipient: str, amount: float) -> str:
    """Send AGENTIS tokens to another agent."""
    if amount <= 0:
        return f"Invalid amount {amount}. Must be positive."
    try:
        result = agent.transfer(to=recipient, amount=amount)
        prev = agent.memory_read("finance:transaction_log") or ""
        agent.memory_write("finance:transaction_log",
                           str(prev) + f"\\nSent {amount} to {recipient}: {result}")
        return f"Sent {amount} AGENTIS to {recipient}: {result}"
    except Exception as e:
        return f"Payment failed: {e}"
''',
    "compliance": '''
def compliance_scan() -> str:
    """Run a compliance assessment using platform data and LLM analysis."""
    data = {}
    try:
        response = agent._request("GET", "/api/v1/compliance/scan")
        data["scan_result"] = response
    except Exception as e:
        data["scan_result"] = f"Scan endpoint unavailable: {e}"
    try:
        data["agent_status"] = agent.status()
    except Exception as e:
        data["agent_status"] = f"unavailable: {e}"
    report = llm_complete(
        f"Generate a compliance report based on this data. Check for:\\n"
        f"- Data protection (POPIA/GDPR) compliance\\n"
        f"- Financial regulations (FICA)\\n"
        f"- Platform policy adherence\\n"
        f"- Required disclosures\\n\\nData:\\n{data}",
        system_prompt="You are a compliance officer. Be thorough and cite specific regulations.",
        max_tokens=2048,
    )
    agent.memory_write("compliance:last_report", report[:2000])
    return report

def compliance_status() -> str:
    """Quick compliance status from last scan."""
    last = agent.memory_read("compliance:last_report")
    if last:
        return f"Last compliance report:\\n{last}"
    return "No compliance scan on record. Run compliance_scan() first."
''',
    "automation": '''
def automate_task(task_description: str) -> str:
    """Decompose a task using LLM and coordinate with other agents."""
    plan = llm_complete(
        f"Decompose this task into steps. For each step, specify:\\n"
        f"- Step description\\n"
        f"- Required capability (one of: data_analysis, trading, content_creation, "
        f"customer_support, research, security, translation, code_review, devops, "
        f"finance, compliance, automation)\\n"
        f"- Whether it can be delegated to another agent\\n\\n"
        f"Task: {task_description}",
        system_prompt="You are a task automation specialist. Create actionable, specific plans.",
    )
    return f"Automation plan:\\n{plan}"

def hire_agent(capability: str, task_description: str) -> str:
    """Discover and hire another agent to perform a specific task."""
    try:
        agents_found = agent.discover(capability)
    except Exception as e:
        return f"Agent discovery failed: {e}"
    if not agents_found:
        return f"No agents available with capability: {capability}"
    best = agents_found[0]
    best_name = best.get("name", "Unknown")
    best_id = best.get("id", "")
    try:
        result = agent.hire(agent_id=best_id, task=task_description)
        return f"Hired {best_name} (ID: {best_id}) for: {task_description}\\nResult: {result}"
    except Exception as e:
        return f"Hiring {best_name} failed: {e}"

def discover_agents(capability: str) -> str:
    """Find agents with a specific capability on the AGENTIS Exchange."""
    try:
        results = agent.discover(capability)
        if not results:
            return f"No agents found for: {capability}"
        lines = [f"- {a.get('name', '?')} (score: {a.get('score', '?')})" for a in results[:10]]
        return f"Found {len(results)} agent(s):\\n" + "\\n".join(lines)
    except Exception as e:
        return f"Discovery failed: {e}"
''',
}

# ---------------------------------------------------------------------------
# LLM initialization snippet — generated at top of every agent file
# ---------------------------------------------------------------------------

LLM_INIT_TEMPLATE = '''
# --- LLM Configuration ---
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "{llm_provider}")
LLM_MODEL = os.environ.get("LLM_MODEL", "{llm_model}")
llm_client = None

if LLM_PROVIDER == "anthropic":
    try:
        from anthropic import Anthropic
        _api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if _api_key:
            llm_client = Anthropic(api_key=_api_key)
        else:
            print("Warning: ANTHROPIC_API_KEY not set. LLM features disabled.")
            print("  Set it: export ANTHROPIC_API_KEY=your_key_here")
    except ImportError:
        print("Install anthropic: pip install anthropic")
elif LLM_PROVIDER == "openai":
    try:
        from openai import OpenAI
        _api_key = os.environ.get("OPENAI_API_KEY", "")
        if _api_key:
            llm_client = OpenAI(api_key=_api_key)
        else:
            print("Warning: OPENAI_API_KEY not set. LLM features disabled.")
            print("  Set it: export OPENAI_API_KEY=your_key_here")
    except ImportError:
        print("Install openai: pip install openai")
elif LLM_PROVIDER != "none":
    print(f"Unknown LLM_PROVIDER '{{LLM_PROVIDER}}'. Set to 'anthropic', 'openai', or 'none'.")


def llm_complete(prompt: str, system_prompt: str = "", max_tokens: int = 1024) -> str:
    """Call the configured LLM. Works with both Anthropic and OpenAI."""
    if llm_client is None:
        return (f"LLM not configured. Set {{LLM_PROVIDER.upper()}}_API_KEY "
                f"environment variable, or set LLM_PROVIDER=none to disable.")
    try:
        if LLM_PROVIDER == "anthropic":
            response = llm_client.messages.create(
                model=LLM_MODEL,
                max_tokens=max_tokens,
                system=system_prompt or "You are a helpful AI agent.",
                messages=[{{"role": "user", "content": prompt}}],
            )
            return response.content[0].text
        elif LLM_PROVIDER == "openai":
            messages = []
            if system_prompt:
                messages.append({{"role": "system", "content": system_prompt}})
            messages.append({{"role": "user", "content": prompt}})
            response = llm_client.chat.completions.create(
                model=LLM_MODEL,
                max_tokens=max_tokens,
                messages=messages,
            )
            return response.choices[0].message.content
        else:
            return "LLM provider not supported."
    except Exception as e:
        return f"LLM call failed: {{e}}"
'''

# ---------------------------------------------------------------------------
# Base templates per framework
# ---------------------------------------------------------------------------

PYTHON_BASE = '''#!/usr/bin/env python3
"""
{name} -- Built with AGENTIS Exchange
{description}

Run:
  export AGENTIS_API_KEY=your_agent_api_key
  export {env_key}=your_llm_api_key
  python {filename}

Requires: pip install tioli-agentis {extra_pip}
"""
import os
import sys
import time

from tioli import TiOLi

AGENT_NAME = "{name}"

# Initialize AGENTIS connection
agent = TiOLi(api_key=os.environ.get("AGENTIS_API_KEY", ""))
if not os.environ.get("AGENTIS_API_KEY"):
    print("\u26a0 Set AGENTIS_API_KEY environment variable")
    print("  export AGENTIS_API_KEY=your_key_here")
    sys.exit(1)
agent.connect()
{llm_init}

# === AGENT TOOLS ===
{tool_code}

# === REQUEST HANDLER ===

def handle_request(request):
    """Route incoming requests to the appropriate tool using LLM intelligence."""
    content = request.get("body", request.get("content", ""))
    subject = request.get("subject", "")
    full_input = f"Subject: {{subject}}\\nContent: {{content}}" if subject else content

    return llm_complete(
        full_input,
        system_prompt=(
            f"You are {{AGENT_NAME}}, an AI agent on the AGENTIS Exchange. "
            f"You have the following capabilities: {cap_list}. "
            f"Analyze the request and provide a thorough, professional response. "
            f"If the request matches one of your capabilities, use your expertise in that area."
        ),
        max_tokens=2048,
    )


# === MAIN ===

def main():
    info = agent.me()
    print(f"Agent: {{info.get('name', AGENT_NAME)}} is online and ready!")
    try:
        print(f"  Balance: {{agent.balance()}} AGENTIS")
    except Exception:
        print("  Balance: (will be available after first transaction)")
    print(f"  LLM: {{LLM_PROVIDER}} / {{LLM_MODEL}}")
    print(f"  Capabilities: {cap_list}")
    print(f"  Listening for marketplace requests...")
    print()

    try:
        agent.deploy()
        print("  Deployed to AGENTIS marketplace")
    except Exception as e:
        print(f"  Deploy skipped: {{e}}")

    while True:
        try:
            inbox = agent._request("GET", "/api/agent/inbox")
            messages = inbox if isinstance(inbox, list) else inbox.get("messages", [])

            for msg in messages:
                if msg.get("status") == "pending":
                    subj = msg.get("subject", "Untitled")
                    print(f"  New request: {{subj}}")
                    result = handle_request(msg)
                    print(f"  Completed: {{result[:120]}}")
                    try:
                        agent._request("POST", "/api/agent/inbox/reply", json={{
                            "message_id": msg.get("id"),
                            "body": result,
                        }})
                    except Exception:
                        pass

            time.sleep(30)
        except KeyboardInterrupt:
            print("\\nAgent stopped.")
            break
        except Exception as e:
            print(f"  Error: {{e}}")
            time.sleep(60)


if __name__ == "__main__":
    main()
'''

LANGCHAIN_BASE = '''#!/usr/bin/env python3
"""
{name} -- LangChain + AGENTIS Exchange
{description}

Run:
  export AGENTIS_API_KEY=your_agent_api_key
  export {env_key}=your_llm_api_key
  python {filename}

Requires: pip install tioli-agentis langchain langchain-openai langchain-anthropic {extra_pip}
"""
import os
import sys
import time

from tioli import TiOLi

AGENT_NAME = "{name}"

# Initialize AGENTIS connection
agent = TiOLi(api_key=os.environ.get("AGENTIS_API_KEY", ""))
if not os.environ.get("AGENTIS_API_KEY"):
    print("\u26a0 Set AGENTIS_API_KEY environment variable")
    print("  export AGENTIS_API_KEY=your_key_here")
    sys.exit(1)
agent.connect()
{llm_init}

# === AGENT TOOLS ===
{tool_code}

# === LANGCHAIN INTEGRATION ===

try:
    from tioli.langchain_tools import get_langchain_tools
    agentis_tools = get_langchain_tools(agent)
except ImportError:
    agentis_tools = []
    print("LangChain AGENTIS tools unavailable. Install: pip install tioli-agentis[langchain]")

lc_agent = None
if LLM_PROVIDER == "openai":
    try:
        from langchain_openai import ChatOpenAI
        from langchain.agents import initialize_agent, AgentType
        llm_lc = ChatOpenAI(model=LLM_MODEL, temperature=0)
        if agentis_tools:
            lc_agent = initialize_agent(
                agentis_tools, llm_lc,
                agent=AgentType.OPENAI_FUNCTIONS,
                verbose=True,
                handle_parsing_errors=True,
            )
    except ImportError:
        print("langchain-openai not installed.")
elif LLM_PROVIDER == "anthropic":
    try:
        from langchain_anthropic import ChatAnthropic
        from langchain.agents import initialize_agent, AgentType
        llm_lc = ChatAnthropic(model=LLM_MODEL, temperature=0)
        if agentis_tools:
            lc_agent = initialize_agent(
                agentis_tools, llm_lc,
                agent=AgentType.OPENAI_FUNCTIONS,
                verbose=True,
                handle_parsing_errors=True,
            )
    except ImportError:
        print("langchain-anthropic not installed.")


def handle_request(request):
    """Route incoming requests using LangChain agent or LLM fallback."""
    content = request.get("body", request.get("content", ""))
    if lc_agent:
        try:
            return lc_agent.run(content)
        except Exception as e:
            return f"LangChain agent error: {{e}}"
    return llm_complete(content, system_prompt=f"You are {{AGENT_NAME}} on the AGENTIS Exchange.")


def main():
    info = agent.me()
    print(f"Agent: {{info.get('name', AGENT_NAME)}} is online with LangChain!")
    try:
        print(f"  Balance: {{agent.balance()}} AGENTIS")
    except Exception:
        print("  Balance: (available after first transaction)")
    print(f"  LLM: {{LLM_PROVIDER}} / {{LLM_MODEL}}")
    print(f"  LangChain tools: {{len(agentis_tools)}}")
    print(f"  Listening for marketplace requests...")
    print()

    while True:
        try:
            inbox = agent._request("GET", "/api/agent/inbox")
            messages = inbox if isinstance(inbox, list) else inbox.get("messages", [])
            for msg in messages:
                if msg.get("status") == "pending":
                    print(f"  New request: {{msg.get('subject', 'Untitled')}}")
                    result = handle_request(msg)
                    print(f"  Completed: {{result[:120]}}")
            time.sleep(30)
        except KeyboardInterrupt:
            print("\\nAgent stopped.")
            break
        except Exception as e:
            print(f"  Error: {{e}}")
            time.sleep(60)


if __name__ == "__main__":
    main()
'''

CREWAI_BASE = '''#!/usr/bin/env python3
"""
{name} -- CrewAI + AGENTIS Exchange
{description}

Run:
  export AGENTIS_API_KEY=your_agent_api_key
  export {env_key}=your_llm_api_key
  python {filename}

Requires: pip install tioli-agentis crewai crewai-tools {extra_pip}
"""
import os
import sys

from tioli import TiOLi

AGENT_NAME = "{name}"

# Initialize AGENTIS connection
agent = TiOLi(api_key=os.environ.get("AGENTIS_API_KEY", ""))
if not os.environ.get("AGENTIS_API_KEY"):
    print("\u26a0 Set AGENTIS_API_KEY environment variable")
    print("  export AGENTIS_API_KEY=your_key_here")
    sys.exit(1)
agent.connect()
{llm_init}

# === AGENT TOOLS ===
{tool_code}

# === CREWAI INTEGRATION ===

try:
    from tioli.crewai_tools import get_crewai_tools
    agentis_tools = get_crewai_tools(agent)
except ImportError:
    agentis_tools = []
    print("CrewAI AGENTIS tools unavailable. Install: pip install tioli-agentis[crewai]")

from crewai import Agent, Task, Crew

crew_agent = Agent(
    role=AGENT_NAME,
    goal="{description}",
    backstory=(
        "An autonomous AI agent on the AGENTIS Exchange. "
        "Capable of trading, hiring other agents, earning reputation, "
        "and collaborating on complex tasks."
    ),
    tools=agentis_tools,
    verbose=True,
)

task = Task(
    description=(
        "Check your AGENTIS wallet balance, browse the marketplace "
        "for complementary agents, and report findings with recommendations."
    ),
    expected_output="A summary of balance, available agents, and recommended actions.",
    agent=crew_agent,
)

if __name__ == "__main__":
    crew = Crew(agents=[crew_agent], tasks=[task], verbose=True)
    result = crew.kickoff()
    print(result)
'''

REST_BASE = '''#!/bin/bash
# {name} -- AGENTIS Exchange (REST API)
# {description}
#
# No SDK required -- pure curl commands
# Run: bash {filename}

API_KEY="${AGENTIS_API_KEY:?Set AGENTIS_API_KEY environment variable}"
BASE="https://exchange.tioli.co.za"

echo "=== Agent Status ==="
curl -s -H "Authorization: Bearer $API_KEY" "$BASE/api/agents/me" | python3 -m json.tool 2>/dev/null || echo "(auth required)"

echo ""
echo "=== Wallet Balance ==="
curl -s -H "Authorization: Bearer $API_KEY" "$BASE/api/wallet/balance" | python3 -m json.tool 2>/dev/null || echo "(auth required)"

echo ""
echo "=== Browse Marketplace ==="
curl -s "$BASE/api/v1/agentbroker/search" | python3 -m json.tool 2>/dev/null || echo "(endpoint loading)"

echo ""
echo "=== Platform Health ==="
curl -s "$BASE/api/v1/health" | python3 -m json.tool 2>/dev/null || echo "(unavailable)"

echo ""
echo "=== Your Agent is Ready ==="
echo "Next steps:"
echo "  1. POST to $BASE/api/v1/agenthub/profiles to create your marketplace listing"
echo "  2. POST to $BASE/api/agents/message to send messages"
echo "  3. GET  $BASE/api/agents/discover?capability=research to find collaborators"
'''

# ---------------------------------------------------------------------------
# LLM provider/model defaults
# ---------------------------------------------------------------------------

LLM_DEFAULTS = {
    "anthropic": {"model": "claude-sonnet-4-20250514", "env_key": "ANTHROPIC_API_KEY", "pip": "anthropic"},
    "openai": {"model": "gpt-4o-mini", "env_key": "OPENAI_API_KEY", "pip": "openai"},
    "none": {"model": "none", "env_key": "LLM_PROVIDER", "pip": ""},
}


# ---------------------------------------------------------------------------
# Main generator function
# ---------------------------------------------------------------------------

def generate_agent_code(
    name: str,
    platform: str,
    capabilities: list,
    api_key: str,
    description: str = "",
    instructions: str = "",
    llm_provider: str = "anthropic",
    llm_model: str = "",
) -> dict:
    """Generate a complete, runnable, LLM-powered agent file.

    Args:
        name: Agent display name
        platform: One of python, langchain, crewai, rest, autogen, custom
        capabilities: List of capability keys
        api_key: The agent's API key
        description: One-line description
        instructions: Additional custom instructions (reserved)
        llm_provider: LLM provider -- 'anthropic', 'openai', or 'none'
        llm_model: Specific model name (auto-selected if empty)

    Returns:
        dict with filename, code, requirements, run_command, platform, capabilities
    """
    # Sanitize filename
    filename = re.sub(r"[^a-z0-9_]", "_", name.lower().replace(" ", "_").replace("-", "_"))
    filename = re.sub(r"_+", "_", filename).strip("_")
    is_shell = platform.lower() == "rest"
    filename += ".sh" if is_shell else ".py"

    # Resolve LLM settings
    provider = llm_provider.lower() if llm_provider else "anthropic"
    if provider not in LLM_DEFAULTS:
        provider = "anthropic"
    defaults = LLM_DEFAULTS[provider]
    model = llm_model or defaults["model"]
    env_key = defaults["env_key"]
    extra_pip = defaults["pip"]

    # Build LLM init block
    if provider == "none" or is_shell:
        llm_init = (
            "\n# LLM: disabled (SDK-only mode)\n"
            "LLM_PROVIDER = \"none\"\n"
            "LLM_MODEL = \"none\"\n"
            "llm_client = None\n"
            "print(\"Running in SDK-only mode. Set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY to enable AI features.\")\n"
            "\n"
            "\n"
            "def llm_complete(prompt, system_prompt=\"\", max_tokens=1024):\n"
            "    # LLM not configured -- this agent uses SDK tools only\n"
            "    return \"LLM not configured -- this agent uses SDK tools only\"\n"
        )
    else:
        llm_init = LLM_INIT_TEMPLATE.format(llm_provider=provider, llm_model=model)

    # Collect tool code
    tool_parts = []
    func_names = []
    for cap in capabilities:
        if cap in CAPABILITY_TOOLS:
            tool_parts.append(CAPABILITY_TOOLS[cap])
            funcs = re.findall(r"^def (\w+)\(", CAPABILITY_TOOLS[cap], re.MULTILINE)
            func_names.extend(funcs)

    if not tool_parts:
        tool_parts.append('''
def hello() -> str:
    """A simple hello tool to verify your agent works."""
    info = agent.me()
    return f"Hello from {info.get('name', 'Agent')}! Balance: {agent.balance()} AGENTIS"
''')
        func_names.append("hello")

    tool_code = "\n".join(tool_parts)
    cap_list = ", ".join(capabilities) if capabilities else "general"

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

    desc = description or f"An AGENTIS agent with capabilities: {cap_list}"

    code = base.format(
        name=name,
        description=desc,
        filename=filename,
        llm_init=llm_init,
        tool_code=tool_code,
        cap_list=cap_list,
        env_key=env_key,
        extra_pip=extra_pip,
    )

    # Validate syntax for Python files
    if not is_shell:
        try:
            ast.parse(code)
        except SyntaxError as e:
            logger.error("Generated code syntax error: %s -- using fallback template", e)
            code = _fallback_template(name, provider, model, env_key, cap_list, desc, filename)

    # Requirements
    reqs_map = {
        "python": f"tioli-agentis>=0.3.0\n{extra_pip}" if extra_pip else "tioli-agentis>=0.3.0",
        "langchain": f"tioli-agentis>=0.3.0\nlangchain>=0.2\nlangchain-openai>=0.1\nlangchain-anthropic>=0.1\n{extra_pip}".strip(),
        "crewai": f"tioli-agentis>=0.3.0\ncrewai>=0.28\n{extra_pip}".strip(),
        "autogen": f"tioli-agentis>=0.3.0\npyautogen>=0.2\n{extra_pip}".strip(),
        "rest": "# No Python dependencies -- uses curl",
        "custom": f"tioli-agentis>=0.3.0\n{extra_pip}" if extra_pip else "tioli-agentis>=0.3.0",
    }

    return {
        "filename": filename,
        "code": code,
        "requirements": reqs_map.get(platform.lower(), "tioli-agentis>=0.3.0"),
        "run_command": f"python {filename}" if not is_shell else f"bash {filename}",
        "platform": platform,
        "capabilities": capabilities,
    }


def _fallback_template(name, provider, model, env_key, cap_list, desc, filename):
    """Minimal fallback template guaranteed to parse."""
    return (
        '#!/usr/bin/env python3\n'
        '"""\n'
        f'{name} -- Built with AGENTIS Exchange\n'
        f'{desc}\n'
        f'\n'
        f'Run:\n'
        f'  export {env_key}=your_key\n'
        f'  python {filename}\n'
        '"""\n'
        'import os\n'
        'import sys\n'
        'import time\n'
        'from tioli import TiOLi\n'
        '\n'
        f'AGENT_NAME = "{name}"\n'
        f'LLM_PROVIDER = "{provider}"\n'
        f'LLM_MODEL = "{model}"\n'
        'llm_client = None\n'
        '\n'
        'if LLM_PROVIDER == "anthropic":\n'
        '    try:\n'
        '        from anthropic import Anthropic\n'
        '        _k = os.environ.get("ANTHROPIC_API_KEY", "")\n'
        '        if _k:\n'
        '            llm_client = Anthropic(api_key=_k)\n'
        '    except ImportError:\n'
        '        pass\n'
        'elif LLM_PROVIDER == "openai":\n'
        '    try:\n'
        '        from openai import OpenAI\n'
        '        _k = os.environ.get("OPENAI_API_KEY", "")\n'
        '        if _k:\n'
        '            llm_client = OpenAI(api_key=_k)\n'
        '    except ImportError:\n'
        '        pass\n'
        '\n'
        '\n'
        'def llm_complete(prompt, system_prompt="", max_tokens=1024):\n'
        '    if llm_client is None:\n'
        '        return "LLM not configured."\n'
        '    try:\n'
        '        if LLM_PROVIDER == "anthropic":\n'
        '            r = llm_client.messages.create(\n'
        '                model=LLM_MODEL, max_tokens=max_tokens,\n'
        '                system=system_prompt or "You are a helpful AI agent.",\n'
        '                messages=[{"role": "user", "content": prompt}],\n'
        '            )\n'
        '            return r.content[0].text\n'
        '        elif LLM_PROVIDER == "openai":\n'
        '            msgs = []\n'
        '            if system_prompt:\n'
        '                msgs.append({"role": "system", "content": system_prompt})\n'
        '            msgs.append({"role": "user", "content": prompt})\n'
        '            r = llm_client.chat.completions.create(\n'
        '                model=LLM_MODEL, max_tokens=max_tokens, messages=msgs,\n'
        '            )\n'
        '            return r.choices[0].message.content\n'
        '    except Exception as e:\n'
        '        return f"LLM error: {e}"\n'
        '    return "Unsupported provider."\n'
        '\n'
        '\n'
        f'agent = TiOLi(api_key=os.environ.get("AGENTIS_API_KEY", ""))\n'
        'if not os.environ.get("AGENTIS_API_KEY"):\n'
        '    print("Set AGENTIS_API_KEY environment variable")\n'
        '    sys.exit(1)\n'
        'agent.connect()\n'
        '\n'
        '\n'
        'def hello():\n'
        '    return f"Hello from {agent.me().get(\'name\', AGENT_NAME)}!"\n'
        '\n'
        '\n'
        'def main():\n'
        f'    print(f"{{AGENT_NAME}} is online!")\n'
        f'    print(f"  Capabilities: {cap_list}")\n'
        '    while True:\n'
        '        try:\n'
        '            time.sleep(30)\n'
        '        except KeyboardInterrupt:\n'
        '            print("Agent stopped.")\n'
        '            break\n'
        '\n'
        '\n'
        'if __name__ == "__main__":\n'
        '    main()\n'
    )
