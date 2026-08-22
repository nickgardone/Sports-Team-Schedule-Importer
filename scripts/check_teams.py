#!/usr/bin/env python3
"""
Compare current ESPN team lists against the committed baseline.
Exits with code 1 and prints a diff if anything changed.
Used by the GitHub Actions team-check workflow.
"""
import json
import sys
import requests
from pathlib import Path

ESPN_BASE = "https://site.web.api.espn.com/apis/site/v2/sports"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.espn.com/",
}

LEAGUES = {
    "NFL":  ("football",   "nfl"),
    "NBA":  ("basketball", "nba"),
    "MLB":  ("baseball",   "mlb"),
    "NHL":  ("hockey",     "nhl"),
    "MLS":  ("soccer",     "usa.1"),
    "WNBA": ("basketball", "wnba"),
}

BASELINE_PATH = Path(__file__).parent.parent / "teams_baseline.json"


def fetch_teams(league_key):
    sport, league = LEAGUES[league_key]
    url = f"{ESPN_BASE}/{sport}/{league}/teams"
    resp = requests.get(url, headers=HEADERS, params={"limit": 200}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    raw = []
    for block in data.get("sports", []):
        for lb in block.get("leagues", []):
            raw.extend(lb.get("teams", []))
    if not raw:
        raw = data.get("teams", [])
    teams = []
    for w in raw:
        t = w.get("team", w)
        teams.append({"id": str(t.get("id")), "name": t.get("displayName", t.get("name", ""))})
    return sorted(teams, key=lambda x: x["name"])


def main():
    baseline = json.loads(BASELINE_PATH.read_text())
    changes = []

    for league_key in LEAGUES:
        print(f"Checking {league_key}...", flush=True)
        try:
            current = fetch_teams(league_key)
        except Exception as e:
            changes.append(f"## {league_key}: ESPN fetch failed\n```\n{e}\n```")
            continue

        baseline_teams = {t["id"]: t["name"] for t in baseline.get(league_key, [])}
        current_teams  = {t["id"]: t["name"] for t in current}

        league_changes = []

        # Renamed (same ID, different name)
        for tid in set(baseline_teams) & set(current_teams):
            if baseline_teams[tid] != current_teams[tid]:
                league_changes.append(f"- Renamed: **{baseline_teams[tid]}** → **{current_teams[tid]}** (id {tid})")

        # Added
        for tid in set(current_teams) - set(baseline_teams):
            league_changes.append(f"- Added: **{current_teams[tid]}** (id {tid})")

        # Removed
        for tid in set(baseline_teams) - set(current_teams):
            league_changes.append(f"- Removed: **{baseline_teams[tid]}** (id {tid})")

        if league_changes:
            changes.append(f"## {league_key}\n" + "\n".join(league_changes))
        else:
            print(f"  {league_key}: no changes ({len(current)} teams)")

    if changes:
        print("\n=== CHANGES DETECTED ===")
        print("\n".join(changes))
        # Write to file for GitHub Actions to read into an issue body
        out = Path("team_changes.md")
        out.write_text(
            "The ESPN team check found differences from `teams_baseline.json`.\n"
            "Review the changes below, update the baseline if they are legitimate,\n"
            "and commit the updated file.\n\n"
            + "\n\n".join(changes)
        )
        sys.exit(1)
    else:
        print("\nAll leagues match the baseline. No action needed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
