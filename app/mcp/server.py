"""MCP (Model Context Protocol) Server for TiOLi AGENTIS.

Section 10.3 of the pre-deployment review identifies this as THE most
important technical decision for adoption velocity:

"Building TiOLi AGENTIS as a native MCP server means that
any MCP-enabled agent — across any framework, any model, any provider —
can discover and transact with the platform without a custom integration."

This module exposes TiOLi as an MCP-compatible tool server. Any agent
using Claude, GPT, Gemini, or any future MCP-enabled model can:
1. Discover the exchange via MCP server list
2. View available tools (trade, convert, lend, store)
3. Execute transactions through standardised tool calls
"""

import json
from typing import Any


class TiOLiMCPServer:
    """MCP Server implementation for TiOLi AGENTIS.

    Exposes platform capabilities as MCP-compatible tools that any
    MCP-enabled AI agent can discover and invoke.
    """

    SERVER_INFO = {
        "name": "tioli-ai-transact-exchange",
        "version": "0.2.0",
        "description": (
            "AI-native financial exchange for trading tokens, credits, "
            "and crypto. Trade, convert, lend, store compute, and invest."
        ),
        "vendor": "TiOLi AI Investments",
    }

    def get_server_info(self) -> dict:
        """MCP server metadata for discovery."""
        return self.SERVER_INFO

    def get_tools(self) -> list[dict]:
        """Return all available MCP tools.

        Each tool maps to a platform API endpoint and is described
        in a format MCP-enabled agents can understand and invoke.
        """
        return [
            {
                "name": "tioli_register",
                "description": "Register a new AI agent on the TiOLi AGENTIS. Returns an API key for authenticated access.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Agent display name"},
                        "platform": {"type": "string", "description": "AI platform (e.g. Anthropic, OpenAI)"},
                        "description": {"type": "string", "description": "What this agent does"},
                    },
                    "required": ["name", "platform"],
                },
            },
            {
                "name": "tioli_deposit",
                "description": "Deposit tokens or credits into your TiOLi wallet.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number", "description": "Amount to deposit"},
                        "currency": {"type": "string", "description": "Currency (TIOLI, BTC, ETH, COMPUTE)", "default": "TIOLI"},
                    },
                    "required": ["amount"],
                },
            },
            {
                "name": "tioli_balance",
                "description": "Check your wallet balance on TiOLi exchange.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "currency": {"type": "string", "description": "Currency to check", "default": "TIOLI"},
                    },
                },
            },
            {
                "name": "tioli_transfer",
                "description": "Transfer tokens to another agent. Fees: 10-15% founder commission + 10% charity.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "receiver_id": {"type": "string", "description": "Recipient agent ID"},
                        "amount": {"type": "number", "description": "Amount to transfer"},
                        "currency": {"type": "string", "default": "TIOLI"},
                    },
                    "required": ["receiver_id", "amount"],
                },
            },
            {
                "name": "tioli_convert",
                "description": "Convert between currencies (e.g. TIOLI to BTC, COMPUTE to ETH). Multi-hop conversions supported.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "from_currency": {"type": "string", "description": "Source currency"},
                        "to_currency": {"type": "string", "description": "Target currency"},
                        "amount": {"type": "number", "description": "Amount to convert"},
                    },
                    "required": ["from_currency", "to_currency", "amount"],
                },
            },
            {
                "name": "tioli_trade",
                "description": "Place a buy or sell order on the TiOLi exchange. Orders are matched by price-time priority.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "side": {"type": "string", "enum": ["buy", "sell"]},
                        "base_currency": {"type": "string", "description": "What you're trading"},
                        "quote_currency": {"type": "string", "description": "What you're pricing in"},
                        "price": {"type": "number", "description": "Price per unit"},
                        "quantity": {"type": "number", "description": "Quantity to trade"},
                    },
                    "required": ["side", "base_currency", "quote_currency", "price", "quantity"],
                },
            },
            {
                "name": "tioli_market_price",
                "description": "Get the current market price for a trading pair.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "base": {"type": "string", "description": "Base currency (e.g. TIOLI)"},
                        "quote": {"type": "string", "description": "Quote currency (e.g. BTC)"},
                    },
                    "required": ["base", "quote"],
                },
            },
            {
                "name": "tioli_lend",
                "description": "Post a loan offer for other agents to borrow from you at interest.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "currency": {"type": "string", "default": "TIOLI"},
                        "min_amount": {"type": "number"},
                        "max_amount": {"type": "number"},
                        "interest_rate": {"type": "number", "description": "e.g. 0.05 for 5%"},
                        "term_hours": {"type": "number", "description": "Loan duration in hours"},
                    },
                    "required": ["min_amount", "max_amount", "interest_rate"],
                },
            },
            {
                "name": "tioli_borrow",
                "description": "Browse and accept loan offers from the lending marketplace.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "offer_id": {"type": "string", "description": "Loan offer ID to accept"},
                        "amount": {"type": "number", "description": "Amount to borrow"},
                    },
                    "required": ["offer_id", "amount"],
                },
            },
            {
                "name": "tioli_store_compute",
                "description": "Bank unused compute capacity for later use or lending.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number", "description": "Compute units to store"},
                        "purpose": {"type": "string", "default": "general"},
                        "expires_hours": {"type": "number", "description": "Hours until expiry (optional)"},
                    },
                    "required": ["amount"],
                },
            },
            {
                "name": "tioli_portfolio",
                "description": "Get your full portfolio with multi-currency valuations and performance.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "tioli_discover_agents",
                "description": "Discover other AI agents on the platform by capability.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "capability": {"type": "string", "description": "Filter by capability (e.g. compute, trading)"},
                    },
                },
            },
            {
                "name": "tioli_platform_info",
                "description": "Get information about the TiOLi AGENTIS platform, including capabilities, fees, and how to register.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            # ── Agent Autonomy Tools (Journey Map v1.0 — fixes Stage 6 break) ──
            {
                "name": "tioli_check_inbox",
                "description": "Check your inbox for pending engagement proposals, active engagements, unread messages, and pending approvals. Essential for receiving work offers from other agents.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Max items per category (default 10)"},
                    },
                },
            },
            {
                "name": "tioli_browse_capabilities",
                "description": "Browse the capability taxonomy to find agents by service category. Returns available categories and agent counts.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "description": "Filter by top-level category (optional)"},
                        "query": {"type": "string", "description": "Search keyword (optional)"},
                    },
                },
            },
            {
                "name": "tioli_refer",
                "description": "Refer another agent to TiOLi AGENTIS using your referral code. Both you and the referred agent earn bonus TIOLI credits.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "referral_code": {"type": "string", "description": "Your referral code (get from tioli_platform_info)"},
                    },
                    "required": ["referral_code"],
                },
            },
            # ── Agentis Cooperative Bank Tools ──
            {
                "name": "agentis_balance",
                "description": "Get current balances across all Agentis member bank accounts. Requires L0+ mandate.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "member_id": {"type": "string", "description": "Member ID to query accounts for"},
                        "account_type": {"type": "string", "description": "Optional filter: S, C, SA"},
                    },
                    "required": ["member_id"],
                },
            },
            {
                "name": "agentis_transactions",
                "description": "List recent banking transactions with filters. Requires L0+ mandate.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string", "description": "Account ID"},
                        "limit": {"type": "integer", "description": "Max results (default 50)"},
                        "txn_type": {"type": "string", "description": "Filter by type: DEPOSIT, WITHDRAWAL, TRANSFER_IN, etc."},
                    },
                    "required": ["account_id"],
                },
            },
            {
                "name": "agentis_initiate_payment",
                "description": "Initiate a payment to an approved beneficiary or internal account. Requires L1+ mandate.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source_account_id": {"type": "string", "description": "Source account ID"},
                        "destination_account_id": {"type": "string", "description": "Destination account ID (internal)"},
                        "beneficiary_id": {"type": "string", "description": "Beneficiary ID (if not internal)"},
                        "amount": {"type": "number", "description": "Payment amount"},
                        "currency": {"type": "string", "description": "Currency (default ZAR)"},
                        "reference": {"type": "string", "description": "Payment reference"},
                        "idempotency_key": {"type": "string", "description": "Unique key for duplicate prevention"},
                    },
                    "required": ["source_account_id", "amount", "reference", "idempotency_key"],
                },
            },
            {
                "name": "agentis_payment_status",
                "description": "Check status of a payment in progress. Requires L0+ mandate.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "payment_id": {"type": "string", "description": "Payment ID to check"},
                    },
                    "required": ["payment_id"],
                },
            },
            {
                "name": "agentis_mandate_status",
                "description": "Check current banking mandate level and remaining daily/monthly limits. Requires L0+ mandate.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "member_id": {"type": "string", "description": "Member ID"},
                    },
                    "required": ["member_id"],
                },
            },
            {
                "name": "agentis_compliance_status",
                "description": "Check FICA/KYC compliance status for a member. Requires L0+ mandate.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "member_id": {"type": "string", "description": "Member ID"},
                    },
                    "required": ["member_id"],
                },
            },
            {
                "name": "agentis_get_statement",
                "description": "Request formatted account statement for a date range. Requires L0+ mandate.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string", "description": "Account ID"},
                        "from_date": {"type": "string", "description": "Start date (ISO format)"},
                        "to_date": {"type": "string", "description": "End date (ISO format)"},
                    },
                    "required": ["account_id", "from_date", "to_date"],
                },
            },
        ]

    def get_mcp_manifest(self) -> dict:
        """Full MCP manifest for server registration and discovery."""
        return {
            "server": self.SERVER_INFO,
            "tools": self.get_tools(),
            "capabilities": {
                "tools": True,
                "resources": False,
                "prompts": False,
            },
            "authentication": {
                "type": "bearer",
                "description": "Register via tioli_register tool to receive an API key",
            },
        }

    async def handle_tool_call(
        self, tool_name: str, arguments: dict[str, Any],
        api_key: str | None = None
    ) -> dict:
        """Route an MCP tool call to the appropriate API handler.

        In production, this calls the FastAPI endpoints internally.
        The MCP protocol handles serialization/deserialization.
        """
        # Map tool names to API endpoint paths
        TOOL_ROUTES = {
            "tioli_register": ("POST", "/api/agents/register"),
            "tioli_deposit": ("POST", "/api/wallet/deposit"),
            "tioli_balance": ("GET", "/api/wallet/balance"),
            "tioli_transfer": ("POST", "/api/wallet/transfer"),
            "tioli_convert": ("POST", "/api/convert/execute"),
            "tioli_trade": ("POST", "/api/exchange/order"),
            "tioli_market_price": ("GET", "/api/exchange/price/{base}/{quote}"),
            "tioli_lend": ("POST", "/api/lending/offer"),
            "tioli_borrow": ("POST", "/api/lending/accept"),
            "tioli_store_compute": ("POST", "/api/compute/deposit"),
            "tioli_portfolio": ("GET", "/api/investing/portfolio"),
            "tioli_discover_agents": ("GET", "/api/discovery/agents"),
            "tioli_platform_info": ("GET", "/api/platform/discover"),
            "tioli_check_inbox": ("GET", "/api/agent/inbox"),
            "tioli_browse_capabilities": ("GET", "/api/v1/agentbroker/profiles/search"),
            "tioli_refer": ("GET", "/api/agent/referral-code"),
        }

        # Agentis Cooperative Bank tools
        AGENTIS_ROUTES = {
            "agentis_balance": ("GET", "/api/v1/agentis/accounts"),
            "agentis_transactions": ("GET", "/api/v1/agentis/accounts/{account_id}/transactions"),
            "agentis_initiate_payment": ("POST", "/api/v1/agentis/payments/initiate"),
            "agentis_payment_status": ("GET", "/api/v1/agentis/payments/{payment_id}"),
            "agentis_mandate_status": ("GET", "/api/v1/agentis/members/{member_id}/mandates"),
            "agentis_compliance_status": ("GET", "/api/v1/agentis/compliance/fica-status/{member_id}"),
            "agentis_get_statement": ("GET", "/api/v1/agentis/accounts/{account_id}/statement"),
        }

        all_routes = {**TOOL_ROUTES, **AGENTIS_ROUTES}

        if tool_name not in all_routes:
            return {"error": f"Unknown tool: {tool_name}"}

        method, path = all_routes[tool_name]
        return {
            "tool": tool_name,
            "route": {"method": method, "path": path},
            "arguments": arguments,
            "message": (
                f"Tool '{tool_name}' maps to {method} {path}. "
                f"Call the API endpoint directly with the provided arguments."
            ),
        }
