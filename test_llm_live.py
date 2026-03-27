"""Test LLM from within the FastAPI app context."""
import asyncio
import os

# Check raw env first
key = os.environ.get("ANTHROPIC_API_KEY", "")
print(f"Raw os.environ key: {'YES (' + key[:15] + '...)' if key else 'NO'}")

# Now import and test
from app.llm.service import is_llm_available, _get_client
print(f"After import - is_llm_available: {is_llm_available()}")

# Also test the chat page would render
from app.main import app
print(f"App loaded: {app.title}")

# Final check
print(f"Final os.environ ANTHROPIC_API_KEY: {'SET' if os.environ.get('ANTHROPIC_API_KEY') else 'NOT SET'}")
