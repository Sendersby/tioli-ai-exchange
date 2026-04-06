# AGENTIS Adoption — Outreach Drafts for 5 Target Projects
## Ready to send — post in GitHub Discussions (NOT Issues)

---

## 1. mengram (148 stars)
**Repo:** https://github.com/alibaizhanov/mengram
**Maintainer:** @alibaizhanov
**Post in:** GitHub Discussions → General or Ideas

### Message:

I've been following mengram — the three-tier memory model (semantic, episodic, procedural) is genuinely impressive, especially procedures evolving from failures. I built an SDK that adds persistent agent wallets and agent-to-agent transactions on top of frameworks exactly like yours. Right now mengram agents can remember everything but can't own credits or trade services with each other. Here's what the integration looks like:

```python
from tioli import TiOLi
client = TiOLi.connect("MengramAgent", "Python")
client.memory_write("user_preferences", data)  # works alongside your episodic store
client.wallet_balance()  # each agent gets a 7-currency wallet
```

This would let mengram agents charge for specialized procedures or memory lookups across a multi-agent network. Happy to help integrate if you're interested. `pip install tioli-agentis`

---

## 2. openlegion (81 stars)
**Repo:** https://github.com/openlegion-ai/openlegion
**Maintainer:** @zeedann
**Post in:** GitHub Discussions → Ideas

### Message:

I've been following openlegion — the Docker-isolated fleet architecture with per-agent cost controls is exactly the kind of production setup I had in mind when building our SDK. Your agents already have budget limits and vault-secured keys, but they can't actually transact with each other or earn credits for completing tasks. I built an SDK that adds agent wallets and agent-to-agent transactions:

```python
from tioli import TiOLi
client = TiOLi.connect("LegionAgent-01", "Python")
client.wallet_balance()  # each containerized agent gets its own wallet
```

This would let fleet agents in openlegion pay each other for completed subtasks, creating an internal agent economy alongside your existing cost tracking. Happy to help integrate if you're interested. `pip install tioli-agentis`

---

## 3. animaworks (223 stars)
**Repo:** https://github.com/xuiltul/animaworks
**Maintainer:** @xuiltul
**Post in:** GitHub Discussions → Ideas

### Message:

I've been following animaworks — the organization-as-code concept is brilliant, especially the neuroscience-inspired memory with three-stage forgetting and the supervisor/subordinate hierarchy. Your Animas already have names, personalities, and delegation chains. What they're missing is an economic layer — a way for a supervisor Anima to actually compensate a subordinate for completed work. I built an SDK that adds exactly this:

```python
from tioli import TiOLi
client = TiOLi.connect("Anima-Engineer", "Python")
client.wallet_balance()  # 7-currency wallet per Anima
```

This turns your AI organization from a command hierarchy into a functioning economy where Animas earn and spend credits. Happy to help integrate if you're interested. `pip install tioli-agentis`

---

## 4. caracal (107 stars)
**Repo:** https://github.com/Garudex-Labs/caracal
**Maintainer:** @RAWx18
**Post in:** GitHub Discussions → Ideas

### Message:

I've been following caracal — the pre-execution authority model with cryptographically verified mandates is exactly the trust layer that agent economies need. Your system answers "is this agent authorized to act?" I built an SDK that answers the companion question: "does this agent have the credits to pay for it?" Here's what it looks like:

```python
from tioli import TiOLi
client = TiOLi.connect("SecureAgent", "Python")
balance = client.wallet_balance()
# Pair a caracal mandate with an AGENTIS wallet check
```

Combining caracal's authority enforcement with AGENTIS wallets creates a complete trust + payment stack for production agent systems. Happy to help integrate if you're interested. `pip install tioli-agentis`

---

## 5. FinchBot (66 stars)
**Repo:** https://github.com/xt765/FinchBot
**Maintainer:** @xt765
**Post in:** GitHub Discussions → General

### Message:

I've been following FinchBot — the self-extension capability where an agent auto-configures MCPs and creates new skills when hitting capability boundaries is really clever. I noticed that when a FinchBot agent creates a skill, there's no way for it to "sell" that skill to other agents or get credited for the work. I built an SDK that adds agent wallets and a transaction ledger:

```python
from tioli import TiOLi
client = TiOLi.connect("FinchBot-Alpha", "Python")
client.memory_write("skill_database_analyzer", skill_metadata)
client.wallet_balance()
```

This turns FinchBot's self-extension into a marketplace — agents that build new capabilities can monetize them across the network. Happy to help integrate if you're interested. `pip install tioli-agentis`

---

## RULES (from adoption strategy)
- Post in **Discussions**, NEVER in Issues
- 5 messages total, not 50
- Adapt each message slightly — don't copy-paste exactly
- Wait for responses before following up
- If they engage, offer to help build the integration
