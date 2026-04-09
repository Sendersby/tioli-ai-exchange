"""Example plugin: Health Alert."""
import logging
log = logging.getLogger("plugin.health_alert")

async def on_health_check_failed(event_data: dict) -> dict:
    """Called when a health check fails."""
    log.warning(f"[health_alert] Platform health degraded: {event_data}")
    return {"alert_sent": True, "event": event_data}
