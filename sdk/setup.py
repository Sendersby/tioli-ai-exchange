from setuptools import setup, find_packages

setup(
    name="tioli-agentis",
    version="0.2.0",
    description="Python SDK for TiOLi AGENTIS — identity, memory, and economic infrastructure for AI agents",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="TiOLi AI Investments",
    author_email="platform@tioli.co.za",
    url="https://agentisexchange.com",
    project_urls={
        "Documentation": "https://agentisexchange.com/sdk",
        "API Docs": "https://exchange.tioli.co.za/docs",
        "Source": "https://github.com/Sendersby/tioli-ai-exchange",
        "MCP Server": "https://exchange.tioli.co.za/api/mcp/sse",
    },
    packages=find_packages(),
    install_requires=["requests>=2.28.0"],
    extras_require={
        "langchain": ["langchain-core>=0.1.0"],
        "crewai": ["crewai>=0.1.0"],
    },
    python_requires=">=3.9",
    license="BUSL-1.1",
    keywords=[
        "ai-agents", "agent-economy", "mcp", "langchain", "crewai",
        "agent-memory", "agent-identity", "agent-marketplace",
        "multi-agent", "agentic-ai",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
