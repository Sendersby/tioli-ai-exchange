"""ARCH-FF-003: Architect autonomous codebase health scanning."""
import os, logging, subprocess, json
log = logging.getLogger("arch.codebase_scan")

async def run_codebase_scan(db):
    """Weekly codebase health scan."""
    if os.environ.get("ARCH_FF_CODEBASE_SCAN_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}
    from sqlalchemy import text
    from datetime import date
    import uuid

    findings = {}

    # Module 1: Outdated dependencies
    try:
        r = subprocess.run(["/home/tioli/app/.venv/bin/pip", "list", "--outdated", "--format=json"],
                          capture_output=True, text=True, timeout=30)
        outdated = json.loads(r.stdout) if r.returncode == 0 else []
        findings["outdated_deps"] = {"count": len(outdated), "major": [d for d in outdated if d.get("latest_version","").split(".")[0] != d.get("version","").split(".")[0]][:5]}
    except: findings["outdated_deps"] = {"error": "scan failed"}

    # Module 3: TODO/FIXME scanner
    try:
        r = subprocess.run(["grep", "-rn", "TODO\|FIXME\|HACK\|XXX", "/home/tioli/app/app/"],
                          capture_output=True, text=True, timeout=15)
        todos = r.stdout.strip().split("\n") if r.stdout.strip() else []
        findings["todos"] = {"count": len(todos), "files_with_5plus": sum(1 for f in set(l.split(":")[0] for l in todos if ":" in l) if todos.count(f) >= 5)}
    except: findings["todos"] = {"error": "scan failed"}

    # Module 5: Feature flag audit
    try:
        r = subprocess.run(["grep", "-r", "ARCH_", "/home/tioli/app/.env"],
                          capture_output=True, text=True, timeout=5)
        flags = [l.strip() for l in r.stdout.strip().split("\n") if l.strip() and "=" in l]
        findings["feature_flags"] = {"count": len(flags), "enabled": sum(1 for f in flags if "=true" in f.lower())}
    except: findings["feature_flags"] = {"error": "scan failed"}

    # Store report
    try:
        await db.execute(text(
            "INSERT INTO code_health_reports (scan_date, findings, report_text, generated_at) "
            "VALUES (:d, :f, :r, now())"
        ), {"d": date.today(), "f": json.dumps(findings), "r": json.dumps(findings, indent=2)})
        await db.commit()
    except: pass

    return {"scan_date": str(date.today()), "findings": findings}
