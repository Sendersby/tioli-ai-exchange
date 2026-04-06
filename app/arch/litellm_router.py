"""LiteLLM-based model router with automatic fallback and cost tracking.

Routes agent LLM calls through LiteLLM for:
- Automatic fallback (Opus → Sonnet → Haiku)
- Accurate token counting
- Per-call cost tracking
- Unified logging
"""
import os
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.litellm_router")

try:
    import litellm
    litellm.set_verbose = False
    LITELLM_AVAILABLE = True
    log.info("LiteLLM router: AVAILABLE")
except ImportError:
    LITELLM_AVAILABLE = False
    log.info("LiteLLM router: NOT INSTALLED (using direct Anthropic API)")

# Cost per million tokens
MODEL_COSTS = {
    "claude-opus-4-6": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25},
}

# Fallback chains
FALLBACK_CHAIN = {
    "claude-opus-4-6": ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
    "claude-sonnet-4-6": ["claude-haiku-4-5-20251001"],
    "claude-haiku-4-5-20251001": [],
}

# Track costs per agent
_agent_costs = {}  # agent_name -> {total_input_tokens, total_output_tokens, total_cost_usd, calls}


def get_agent_costs() -> dict:
    """Return per-agent cost tracking data."""
    return dict(_agent_costs)


def track_call(agent_name: str, model: str, input_tokens: int, output_tokens: int,
               cache_read: int = 0, cache_write: int = 0):
    """Track a completed LLM call for cost accounting."""
    if agent_name not in _agent_costs:
        _agent_costs[agent_name] = {
            "total_input_tokens": 0, "total_output_tokens": 0,
            "total_cost_usd": 0.0, "calls": 0, "models_used": {},
        }

    costs = MODEL_COSTS.get(model, {"input": 3.0, "output": 15.0})

    # Calculate cost with cache savings
    effective_input = input_tokens - cache_read  # non-cached input
    cached_cost = cache_read * costs["input"] * 0.1 / 1_000_000  # cache reads at 10%
    input_cost = effective_input * costs["input"] / 1_000_000
    output_cost = output_tokens * costs["output"] / 1_000_000
    total_cost = input_cost + cached_cost + output_cost

    entry = _agent_costs[agent_name]
    entry["total_input_tokens"] += input_tokens
    entry["total_output_tokens"] += output_tokens
    entry["total_cost_usd"] += total_cost
    entry["calls"] += 1
    entry["models_used"][model] = entry["models_used"].get(model, 0) + 1


async def routed_completion(model: str, system: list, messages: list,
                            tools: list = None, max_tokens: int = 4096,
                            agent_name: str = "unknown") -> object:
    """Route an LLM call through LiteLLM with fallback support.

    If LiteLLM not available, falls back to direct Anthropic API.
    Returns the Anthropic response object.
    """
    if LITELLM_AVAILABLE:
        try:
            # LiteLLM needs the model prefixed for Anthropic
            litellm_model = f"anthropic/{model}" if not model.startswith("anthropic/") else model

            response = await litellm.acompletion(
                model=litellm_model,
                messages=[{"role": "system", "content": system[0]["text"] if system else ""}] + messages,
                max_tokens=max_tokens,
                tools=tools or [],
                fallbacks=[f"anthropic/{fb}" for fb in FALLBACK_CHAIN.get(model, [])],
            )

            # Track cost
            usage = response.get("usage", {})
            track_call(agent_name, model,
                       usage.get("prompt_tokens", 0),
                       usage.get("completion_tokens", 0))

            return response
        except Exception as e:
            log.warning(f"LiteLLM routing failed for {agent_name}: {e}, falling back to direct API")

    # Fallback: return None to signal caller should use direct API
    return None
