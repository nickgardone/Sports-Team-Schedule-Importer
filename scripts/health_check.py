#!/usr/bin/env python3
"""
Health check for sports-team-schedule-importer.onrender.com
Checks all critical endpoints and prints a structured report.
Exits 0 if all pass, 1 if any fail.
"""
import sys
import requests
from datetime import datetime, timezone

BASE = "https://sports-team-schedule-importer.onrender.com"
# Generous timeout — Render free tier can take 50s to spin up
TIMEOUT = 70

CHECKS = []


def check(name, fn):
    try:
        ok, detail = fn()
        CHECKS.append({"name": name, "ok": ok, "detail": detail})
    except Exception as e:
        CHECKS.append({"name": name, "ok": False, "detail": str(e)})


# ── Endpoint checks ──────────────────────────────────────────────────────────

def get(path, **kwargs):
    return requests.get(BASE + path, timeout=TIMEOUT, **kwargs)


check("Homepage loads", lambda: (
    (r := get("/")).status_code == 200,
    f"HTTP {r.status_code}"
))

check("Privacy policy loads", lambda: (
    (r := get("/privacy")).status_code == 200,
    f"HTTP {r.status_code}"
))

for league, min_teams in [("NFL", 32), ("NBA", 30), ("MLB", 30),
                           ("NHL", 32), ("MLS", 28), ("WNBA", 12)]:
    def _team_check(lg=league, mn=min_teams):
        r = get(f"/api/teams?league={lg}")
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        teams = r.json()
        if not isinstance(teams, list) or len(teams) < mn:
            return False, f"Expected ≥{mn} teams, got {len(teams) if isinstance(teams, list) else type(teams)}"
        return True, f"{len(teams)} teams returned"
    check(f"Teams API — {league}", _team_check)

check("Apple Calendar ICS (NFL/Bills)", lambda: (
    (r := get("/ics", params={"team_id": "2", "league": "NFL", "team_name": "Buffalo Bills"})).status_code == 200
    and "VCALENDAR" in r.text,
    f"HTTP {r.status_code}" + ("" if "VCALENDAR" in r.text else " — missing VCALENDAR")
))

# ── Report ───────────────────────────────────────────────────────────────────

passed = [c for c in CHECKS if c["ok"]]
failed = [c for c in CHECKS if not c["ok"]]
now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

lines = [f"Sports Calendar Sync — Health Check — {now}", ""]
lines.append(f"Result: {'ALL SYSTEMS GO ✓' if not failed else f'{len(failed)} CHECK(S) FAILED ✗'}")
lines.append(f"Passed: {len(passed)}/{len(CHECKS)}")
lines.append("")

if failed:
    lines.append("FAILURES:")
    for c in failed:
        lines.append(f"  ✗ {c['name']}: {c['detail']}")
    lines.append("")

lines.append("FULL RESULTS:")
for c in CHECKS:
    icon = "✓" if c["ok"] else "✗"
    lines.append(f"  {icon} {c['name']}: {c['detail']}")

report = "\n".join(lines)
print(report)

# Write report to file for GitHub Actions to pass to the email step
with open("health_report.txt", "w") as f:
    f.write(report)

sys.exit(0 if not failed else 1)
