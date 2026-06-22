#!/usr/bin/env python3
"""
Generate a combined GitHub stats SVG for TSayles-plt + tsayles.

Historical PLT contributions from @tsayles are stored in
scripts/tsayles_baseline.json (captured before account was removed
from the PowerLightTech org).  Only @TSayles-plt is queried live.

Usage:
  # Normal weekly run (uses baseline file):
  python scripts/generate_stats.py

  # One-time baseline capture (run while tsayles still has org access):
  python scripts/generate_stats.py --capture-baseline

Requires GH_TOKEN env var — a fine-grained PAT with Contents: Read-only
on PowerLightTech repos (only needed for --capture-baseline; normal runs
only query TSayles-plt).
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import requests

GRAPHQL_URL = "https://api.github.com/graphql"
PLT_ORG = "powerlighttech"
BASELINE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "tsayles_baseline.json",
)

QUERY = """
query UserStats($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      commitContributionsByRepository(maxRepositories: 100) {
        repository {
          owner { login }
          stargazerCount
        }
        contributions { totalCount }
      }
      pullRequestContributionsByRepository(maxRepositories: 100) {
        repository { owner { login } }
        contributions { totalCount }
      }
      issueContributionsByRepository(maxRepositories: 100) {
        repository { owner { login } }
        contributions { totalCount }
      }
    }
  }
}
"""


def query_github(token: str, login: str) -> dict:
    headers = {"Authorization": f"bearer {token}"}
    resp = requests.post(
        GRAPHQL_URL,
        json={"query": QUERY, "variables": {"login": login}},
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(
            f"GraphQL errors for {login}: {data['errors']}"
        )
    return data["data"]["user"]["contributionsCollection"]


def _is_plt(repo_node: dict) -> bool:
    return repo_node["owner"]["login"].lower() == PLT_ORG


def filter_plt(col: dict) -> dict:
    """Return contribution counts scoped to PowerLightTech org only."""
    commits = sum(
        r["contributions"]["totalCount"]
        for r in col["commitContributionsByRepository"]
        if _is_plt(r["repository"])
    )
    prs = sum(
        r["contributions"]["totalCount"]
        for r in col["pullRequestContributionsByRepository"]
        if _is_plt(r["repository"])
    )
    issues = sum(
        r["contributions"]["totalCount"]
        for r in col["issueContributionsByRepository"]
        if _is_plt(r["repository"])
    )
    stars = sum(
        r["repository"]["stargazerCount"]
        for r in col["commitContributionsByRepository"]
        if _is_plt(r["repository"])
    )
    return {"commits": commits, "prs": prs, "issues": issues,
            "stars": stars}


def extract_all(col: dict) -> dict:
    """Return contribution counts across all repos."""
    commits = col["totalCommitContributions"]
    prs = col["totalPullRequestContributions"]
    issues = col["totalIssueContributions"]
    stars = sum(
        r["repository"]["stargazerCount"]
        for r in col["commitContributionsByRepository"]
    )
    return {"commits": commits, "prs": prs, "issues": issues,
            "stars": stars}


def load_baseline() -> dict:
    if not os.path.exists(BASELINE_FILE):
        print(
            "WARNING: tsayles_baseline.json not found — "
            "run with --capture-baseline first. Using zeros.",
            file=sys.stderr,
        )
        return {"commits": 0, "prs": 0, "issues": 0, "stars": 0}
    with open(BASELINE_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def capture_baseline(token: str) -> None:
    print("Fetching tsayles PLT contributions (baseline capture)...")
    col = query_github(token, "tsayles")
    stats = filter_plt(col)
    stats["captured_at"] = datetime.now(timezone.utc).isoformat()
    with open(BASELINE_FILE, "w", encoding="utf-8") as fh:
        json.dump(stats, fh, indent=2)
    print(f"Baseline saved to {BASELINE_FILE}:")
    print(json.dumps(stats, indent=2))


def render_svg(stats: dict, updated: str) -> str:
    c = f"{stats['commits']:,}"
    p = f"{stats['prs']:,}"
    i = f"{stats['issues']:,}"
    s = f"{stats['stars']:,}"
    return f"""\
<svg width="495" height="175" viewBox="0 0 495 175"
  xmlns="http://www.w3.org/2000/svg">
  <style>
    .bg    {{ fill:#fff; stroke:#e4e2e2; stroke-width:1; }}
    .title {{ font:600 16px "Segoe UI",Ubuntu,Sans-Serif; fill:#2f80ed; }}
    .val   {{ font:700 22px "Segoe UI",Ubuntu,Sans-Serif; fill:#333; }}
    .lbl   {{ font:400 12px "Segoe UI",Ubuntu,Sans-Serif; fill:#555; }}
    .note  {{ font:400 11px "Segoe UI",Ubuntu,Sans-Serif; fill:#999; }}
  </style>
  <rect class="bg" x="0.5" y="0.5" width="494" height="174" rx="4.5"/>
  <text x="25" y="35" class="title">
    TJ Sayles &#8212; PLT Contributions (past year)
  </text>
  <text x="55"  y="88" class="val">{c}</text>
  <text x="55"  y="105" class="lbl">Commits</text>
  <text x="175" y="88" class="val">{p}</text>
  <text x="175" y="105" class="lbl">Pull Requests</text>
  <text x="315" y="88" class="val">{i}</text>
  <text x="315" y="105" class="lbl">Issues</text>
  <text x="415" y="88" class="val">{s}</text>
  <text x="415" y="105" class="lbl">Stars</text>
  <text x="25" y="138" class="note">
    @TSayles-plt (Jun 2026+) + @tsayles baseline (PowerLightTech, prior work)
  </text>
  <text x="25" y="155" class="note">Updated: {updated}</text>
</svg>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--capture-baseline",
        action="store_true",
        help="Fetch and save tsayles PLT contribution baseline.",
    )
    args = parser.parse_args()

    token = os.environ.get("GH_TOKEN")
    if not token:
        print("ERROR: GH_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    if args.capture_baseline:
        capture_baseline(token)
        return

    print("Fetching TSayles-plt contributions (live)...")
    new_stats = extract_all(query_github(token, "TSayles-plt"))

    print("Loading tsayles baseline (static)...")
    old_stats = load_baseline()

    combined = {
        "commits": new_stats["commits"] + old_stats["commits"],
        "prs":     new_stats["prs"]     + old_stats["prs"],
        "issues":  new_stats["issues"]  + old_stats["issues"],
        "stars":   new_stats["stars"]   + old_stats["stars"],
    }
    print(f"Combined: {combined}")

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    svg = render_svg(combined, updated)

    repo_root = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
    out_path = os.path.join(repo_root, "stats.svg")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"Written: {out_path}")


if __name__ == "__main__":
    main()

