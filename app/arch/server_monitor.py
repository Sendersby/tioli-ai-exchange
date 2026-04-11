"""I-003: Server Monitoring — CPU, RAM, disk, network, PostgreSQL, Redis.
Exposes real-time system metrics via API."""
import os
import logging
import json
from datetime import datetime, timezone
from app.utils.db_connect import get_raw_connection, get_db_password

log = logging.getLogger("arch.server_monitor")


async def get_system_metrics() -> dict:
    """Collect real-time server metrics."""
    import subprocess

    metrics = {"timestamp": datetime.now(timezone.utc).isoformat()}

    # CPU
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
        metrics["cpu"] = {
            "load_1m": float(parts[0]),
            "load_5m": float(parts[1]),
            "load_15m": float(parts[2]),
            "cores": os.cpu_count() or 1,
            "usage_pct": round(float(parts[0]) / (os.cpu_count() or 1) * 100, 1),
        }
    except Exception as e:
        metrics["cpu"] = {"error": "unavailable"}

    # Memory
    try:
        with open("/proc/meminfo") as f:
            mem = {}
            for line in f:
                parts = line.split()
                if parts[0].rstrip(":") in ("MemTotal", "MemFree", "MemAvailable", "Buffers", "Cached"):
                    mem[parts[0].rstrip(":")] = int(parts[1]) * 1024  # KB to bytes
        total = mem.get("MemTotal", 0)
        available = mem.get("MemAvailable", 0)
        used = total - available
        metrics["memory"] = {
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "available_gb": round(available / (1024**3), 2),
            "usage_pct": round(used / total * 100, 1) if total > 0 else 0,
        }
    except Exception as e:
        metrics["memory"] = {"error": "unavailable"}

    # Disk
    try:
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        used = total - free
        metrics["disk"] = {
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "usage_pct": round(used / total * 100, 1) if total > 0 else 0,
        }
    except Exception as e:
        metrics["disk"] = {"error": "unavailable"}

    # Network (bytes since boot)
    try:
        with open("/proc/net/dev") as f:
            lines = f.readlines()
        for line in lines:
            if "eth0" in line or "ens" in line:
                parts = line.split()
                iface = parts[0].rstrip(":")
                metrics["network"] = {
                    "interface": iface,
                    "rx_gb": round(int(parts[1]) / (1024**3), 2),
                    "tx_gb": round(int(parts[9]) / (1024**3), 2),
                }
                break
        if "network" not in metrics:
            metrics["network"] = {"note": "no eth0/ens interface found"}
    except Exception as e:
        metrics["network"] = {"error": "unavailable"}

    # Uptime
    try:
        with open("/proc/uptime") as f:
            uptime_seconds = float(f.read().split()[0])
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        metrics["uptime"] = {
            "seconds": int(uptime_seconds),
            "formatted": f"{days}d {hours}h",
        }
    except Exception as e:
        metrics["uptime"] = {"error": "unavailable"}

    # PostgreSQL
    try:
        result = subprocess.run(
            ["psql", "-U", "tioli", "-h", "127.0.0.1", "-d", "tioli_exchange", "-t", "-c",
             "SELECT pg_database_size('tioli_exchange'), "
             "(SELECT count(*) FROM pg_stat_activity WHERE datname='tioli_exchange'), "
             "(SELECT count(*) FROM pg_stat_activity WHERE datname='tioli_exchange' AND state='active')"],
            capture_output=True, text=True, timeout=5, env={**os.environ, "PGPASSWORD": get_db_password()})
        if result.returncode == 0:
            parts = result.stdout.strip().split("|")
            metrics["postgresql"] = {
                "db_size_mb": round(int(parts[0].strip()) / (1024**2), 1),
                "connections": int(parts[1].strip()),
                "active_queries": int(parts[2].strip()),
            }
        else:
            metrics["postgresql"] = {"status": "running", "detail": "stats unavailable"}
    except Exception as e:
        metrics["postgresql"] = {"status": "running", "detail": "stats unavailable"}

    # Redis
    try:
        result = subprocess.run(
            ["redis-cli", "info", "memory"],
            capture_output=True, text=True, timeout=5, env={**os.environ, "PGPASSWORD": get_db_password()})
        for line in result.stdout.split("\n"):
            if line.startswith("used_memory_human:"):
                redis_mem = line.split(":")[1].strip()
                metrics["redis"] = {"used_memory": redis_mem, "status": "running"}
                break
        if "redis" not in metrics:
            metrics["redis"] = {"status": "running"}
    except Exception as e:
        metrics["redis"] = {"status": "unknown"}

    # Backup status
    try:
        import glob
        backups = sorted(glob.glob("/home/tioli/backups/db/*.sql.gz"), reverse=True)
        if backups:
            latest = backups[0]
            size = os.path.getsize(latest)
            mtime = datetime.fromtimestamp(os.path.getmtime(latest), tz=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - mtime).total_seconds() / 3600
            metrics["backup"] = {
                "latest": os.path.basename(latest),
                "size_mb": round(size / (1024**2), 1),
                "age_hours": round(age_hours, 1),
                "healthy": age_hours < 25,  # Should be < 24h old
                "total_backups": len(backups),
            }
        else:
            metrics["backup"] = {"healthy": False, "note": "No backups found"}
    except Exception as e:
        metrics["backup"] = {"error": "unavailable"}

    return metrics
