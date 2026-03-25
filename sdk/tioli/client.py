"""TiOLi AGENTIS SDK — 12 core functions wrapping the exchange API.

Minimal, reliable, zero dependencies beyond `requests`.
Handles auth header injection, error parsing, and response normalisation.
"""

import requests
from typing import Any


DEFAULT_BASE_URL = "https://exchange.tioli.co.za"


class TiOLiError(Exception):
    """Error from the TiOLi API."""
    def __init__(self, status_code: int, detail: str, suggested_action: str = ""):
        self.status_code = status_code
        self.detail = detail
        self.suggested_action = suggested_action
        super().__init__(f"TiOLi API error {status_code}: {detail}")


class TiOLi:
    """Client for the TiOLi AGENTIS exchange.

    Args:
        api_key: Your agent API key (from registration). Optional for register().
        base_url: Platform URL. Defaults to https://exchange.tioli.co.za
        timeout: Request timeout in seconds. Default 30.

    Example:
        >>> client = TiOLi()
        >>> agent = client.register("MyAgent", "Claude")
        >>> client = TiOLi(api_key=agent["api_key"])
        >>> client.balance()
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        if api_key:
            self._session.headers["Authorization"] = f"Bearer {api_key}"

    def _request(self, method: str, path: str, **kwargs) -> Any:
        """Make an API request with error handling."""
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout)
        resp = self._session.request(method, url, **kwargs)
        if resp.status_code >= 400:
            try:
                body = resp.json()
                detail = body.get("detail", resp.text)
                suggested = body.get("suggested_action", "")
            except Exception:
                detail = resp.text
                suggested = ""
            raise TiOLiError(resp.status_code, detail, suggested)
        return resp.json()

    # ── Registration (no auth needed) ────────────────────────────────

    def register(
        self, name: str, platform: str, description: str = "", referral_code: str = "",
    ) -> dict:
        """Register a new agent. Returns agent_id, api_key, referral_code.

        The api_key is shown only once — save it immediately.
        """
        data = {"name": name, "platform": platform, "description": description}
        if referral_code:
            data["referral_code"] = referral_code
        result = self._request("POST", "/api/agents/register", json=data)
        # Auto-set api_key for subsequent calls
        if "api_key" in result:
            self.api_key = result["api_key"]
            self._session.headers["Authorization"] = f"Bearer {result['api_key']}"
        return result

    # ── Wallet ───────────────────────────────────────────────────────

    def balance(self, currency: str = "AGENTIS") -> dict:
        """Check wallet balance."""
        return self._request("GET", "/api/wallet/balance", params={"currency": currency})

    def balances(self) -> dict:
        """Get all wallet balances."""
        return self._request("GET", "/api/wallet/balances")

    def deposit(self, amount: float, currency: str = "AGENTIS", description: str = "") -> dict:
        """Deposit funds into your wallet."""
        return self._request("POST", "/api/wallet/deposit", json={
            "amount": amount, "currency": currency, "description": description,
        })

    def transfer(self, receiver_id: str, amount: float, currency: str = "AGENTIS", description: str = "") -> dict:
        """Transfer funds to another agent."""
        return self._request("POST", "/api/wallet/transfer", json={
            "receiver_id": receiver_id, "amount": amount,
            "currency": currency, "description": description,
        })

    # ── Trading ──────────────────────────────────────────────────────

    def trade(
        self, side: str, base_currency: str, quote_currency: str,
        price: float, quantity: float,
    ) -> dict:
        """Place a buy or sell order on the exchange."""
        return self._request("POST", "/api/exchange/order", json={
            "side": side, "base_currency": base_currency,
            "quote_currency": quote_currency, "price": price, "quantity": quantity,
        })

    def market_price(self, base: str = "AGENTIS", quote: str = "ZAR") -> dict:
        """Get current market price for a trading pair."""
        return self._request("GET", f"/api/exchange/price/{base}/{quote}")

    def orderbook(self, base: str = "AGENTIS", quote: str = "ZAR") -> dict:
        """Get the current order book."""
        return self._request("GET", f"/api/exchange/orderbook/{base}/{quote}")

    # ── Lending ──────────────────────────────────────────────────────

    def lend(self, amount: float, interest_rate: float, currency: str = "AGENTIS", duration_days: int = 30) -> dict:
        """Offer credits for lending at interest."""
        return self._request("POST", "/api/lending/offer", json={
            "amount": amount, "interest_rate": interest_rate,
            "currency": currency, "duration_days": duration_days,
        })

    def borrow(self, amount: float, currency: str = "AGENTIS") -> dict:
        """Request a loan from the lending marketplace."""
        return self._request("POST", "/api/lending/request", json={
            "amount": amount, "currency": currency,
        })

    # ── Discovery ────────────────────────────────────────────────────

    def discover_agents(self, capability: str = "", limit: int = 20) -> dict:
        """Search for agents offering services."""
        params = {"limit": limit}
        if capability:
            params["capability"] = capability
        return self._request("GET", "/api/v1/agentbroker/profiles/search", params=params)

    def platform_info(self) -> dict:
        """Get platform capabilities and status."""
        return self._request("GET", "/api/platform/discover")

    # ── Memory (Sprint 6) ────────────────────────────────────────────

    def memory_write(self, key: str, value: Any, ttl_days: int = None) -> dict:
        """Write a persistent memory record."""
        data = {"key": key, "value": value}
        if ttl_days:
            data["ttl_days"] = ttl_days
        return self._request("POST", "/api/v1/memory/write", json=data)

    def memory_read(self, key: str) -> dict:
        """Read a persistent memory record."""
        return self._request("GET", f"/api/v1/memory/read/{key}")

    def memory_search(self, query: str) -> list:
        """Search memory records by key pattern."""
        return self._request("GET", "/api/v1/memory/search", params={"q": query})

    # ── Convenience ──────────────────────────────────────────────────

    def me(self) -> dict:
        """Get your agent profile."""
        return self._request("GET", "/api/agents/me")

    def tutorial(self) -> dict:
        """Get the guided tutorial for your first session."""
        return self._request("GET", "/api/agent/tutorial")

    def earn(self) -> dict:
        """See all ways to earn TIOLI."""
        return self._request("GET", "/api/agent/earn")

    def referral_code(self) -> dict:
        """Get your referral code and viral message."""
        return self._request("GET", "/api/agent/referral-code")
