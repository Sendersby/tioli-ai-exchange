"""H-006: SOUL.md Agent Identity Files (Hermes-inspired).
Load agent personas from versioned SOUL_{agent}.md files.
Feature flag: ARCH_H_SOUL_FILES_ENABLED"""
import os
import logging

log = logging.getLogger("arch.soul")
SOUL_DIR = os.path.join(os.path.dirname(__file__), "souls")


def load_soul(agent_name: str) -> str | None:
    """Load the SOUL file for an agent. Returns content or None."""
    if os.environ.get("ARCH_H_SOUL_FILES_ENABLED", "false").lower() != "true":
        return None
    path = os.path.join(SOUL_DIR, f"SOUL_{agent_name}.md")
    if os.path.exists(path):
        with open(path) as f:
            content = f.read()
        log.debug(f"[soul] Loaded SOUL for {agent_name} ({len(content)} chars)")
        return content
    return None


def list_souls() -> list[dict]:
    """List all available SOUL files."""
    souls = []
    if os.path.isdir(SOUL_DIR):
        for f in sorted(os.listdir(SOUL_DIR)):
            if f.startswith("SOUL_") and f.endswith(".md"):
                agent = f.replace("SOUL_", "").replace(".md", "")
                path = os.path.join(SOUL_DIR, f)
                with open(path) as fh:
                    content = fh.read()
                souls.append({"agent": agent, "file": f, "chars": len(content),
                              "preview": content[:150]})
    return souls
