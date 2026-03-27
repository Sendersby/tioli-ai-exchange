import os
from app.llm.service import is_llm_available, _get_client

key = os.environ.get("ANTHROPIC_API_KEY", "")
print(f"Key in env: {bool(key)}")
print(f"Key prefix: {key[:15]}..." if key else "Key: EMPTY")
print(f"is_llm_available: {is_llm_available()}")
client = _get_client()
print(f"Client created: {client is not None}")
