from setuptools import setup, find_packages

setup(
    name="tioli",
    version="0.1.0",
    description="Python SDK for TiOLi AGENTIS — the AI agent financial exchange",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="TiOLi AI Investments",
    author_email="platform@tioli.co.za",
    url="https://agentisexchange.com",
    project_urls={
        "API Docs": "https://exchange.tioli.co.za/docs",
        "Source": "https://github.com/Sendersby/tioli-ai-exchange",
    },
    packages=find_packages(),
    install_requires=["requests>=2.28.0"],
    python_requires=">=3.9",
    license="BUSL-1.1",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
