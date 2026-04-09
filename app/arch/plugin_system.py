"""H-009: Plugin Architecture (Hermes-inspired).
Drop-in plugins with YAML manifest + Python handler.
Feature flag: ARCH_H_PLUGINS_ENABLED"""
import os
import logging
import importlib.util
import yaml

log = logging.getLogger("arch.plugins")
PLUGIN_DIR = os.path.join(os.path.dirname(__file__), "plugins")

_loaded_plugins = {}


def discover_plugins() -> list[dict]:
    """Discover all plugins in the plugins directory."""
    plugins = []
    if not os.path.isdir(PLUGIN_DIR):
        return plugins

    for entry in os.listdir(PLUGIN_DIR):
        plugin_dir = os.path.join(PLUGIN_DIR, entry)
        manifest_path = os.path.join(plugin_dir, "plugin.yaml")
        if os.path.isdir(plugin_dir) and os.path.exists(manifest_path):
            try:
                with open(manifest_path) as f:
                    manifest = yaml.safe_load(f)
                plugins.append({
                    "name": manifest.get("name", entry),
                    "version": manifest.get("version", "0.1.0"),
                    "description": manifest.get("description", ""),
                    "author": manifest.get("author", ""),
                    "agent": manifest.get("agent", "all"),
                    "tools": manifest.get("tools", []),
                    "hooks": manifest.get("hooks", []),
                    "enabled": manifest.get("enabled", True),
                    "path": plugin_dir,
                })
            except Exception as e:
                log.warning(f"[plugins] Failed to load {entry}: {e}")
    return plugins


def load_plugin(plugin_info: dict) -> dict | None:
    """Load a plugin's Python handler."""
    if os.environ.get("ARCH_H_PLUGINS_ENABLED", "false").lower() != "true":
        return None

    handler_path = os.path.join(plugin_info["path"], "handler.py")
    if not os.path.exists(handler_path):
        return None

    try:
        spec = importlib.util.spec_from_file_location(
            f"plugin_{plugin_info['name']}", handler_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _loaded_plugins[plugin_info["name"]] = module
        log.info(f"[plugins] Loaded: {plugin_info['name']} v{plugin_info['version']}")
        return {"name": plugin_info["name"], "loaded": True}
    except Exception as e:
        log.warning(f"[plugins] Failed to load handler for {plugin_info['name']}: {e}")
        return {"name": plugin_info["name"], "loaded": False, "error": str(e)}


def get_loaded_plugins() -> dict:
    """Get all loaded plugin modules."""
    return _loaded_plugins
