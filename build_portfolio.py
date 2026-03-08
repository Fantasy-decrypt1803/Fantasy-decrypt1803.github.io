"""
build_portfolio.py
Fetches live GitHub data and bakes it into the portfolio HTML.
Run this whenever you want to update the static site with fresh stats.

Usage:
    python build_portfolio.py
    python build_portfolio.py --username YOUR_GITHUB_USERNAME
    python build_portfolio.py --token YOUR_GITHUB_TOKEN   (higher rate limits)

Output:
    portfolio/index.html   ← production-ready static file
    portfolio/             ← open index.html in browser or deploy to GitHub Pages
"""

import requests
import json
import argparse
import re
import sys
from pathlib import Path
from datetime import datetime

# ── Config ────────────────────────────────────────────────────
USERNAME = "Fantasy-decrypt1803"

PORTFOLIO_REPOS = [
    "financial-index-etl",
    "financial-recon-tool",
    "asset-class-dashboard",
    "uat-test-framework",
]

TEMPLATE_PATH = Path(__file__).parent / "portfolio" / "index.html"
OUTPUT_PATH   = Path(__file__).parent / "portfolio" / "index.html"


# ── GitHub API client ─────────────────────────────────────────
class GitHubClient:
    BASE = "https://api.github.com"

    def __init__(self, username: str, token: str = None):
        self.username = username
        self.headers = {"Accept": "application/vnd.github+json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def get(self, endpoint: str) -> dict | list | None:
        url = f"{self.BASE}{endpoint}"
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 404:
                print(f"  [404] Not found: {endpoint}")
            elif r.status_code == 403:
                print(f"  [403] Rate limited — pass --token to increase limits")
            return None
        except requests.RequestException as e:
            print(f"  [ERROR] {url}: {e}")
            return None

    def user(self) -> dict:
        return self.get(f"/users/{self.username}") or {}

    def repos(self) -> list:
        return self.get(f"/users/{self.username}/repos?per_page=100&sort=updated") or []

    def repo(self, name: str) -> dict:
        return self.get(f"/repos/{self.username}/{name}") or {}

    def languages(self, name: str) -> dict:
        return self.get(f"/repos/{self.username}/{name}/languages") or {}

    def commits(self, name: str) -> list:
        return self.get(f"/repos/{self.username}/{name}/commits?per_page=1") or []


# ── Fetch all data ────────────────────────────────────────────
def fetch_portfolio_data(client: GitHubClient) -> dict:
    print(f"\n  Fetching GitHub data for @{client.username}...\n")

    # ── User profile ──────────────────────────────────────────
    user = client.user()
    print(f"  [USER]  {user.get('name', USERNAME)} — {user.get('public_repos', '?')} repos")

    # ── All repos ─────────────────────────────────────────────
    all_repos = client.repos()
    total_stars = sum(r.get("stargazers_count", 0) for r in all_repos)
    total_forks = sum(r.get("forks_count", 0) for r in all_repos)
    print(f"  [REPOS] {len(all_repos)} repos · {total_stars} stars · {total_forks} forks")

    # ── Portfolio repos detail ────────────────────────────────
    repo_data = {}
    for repo_name in PORTFOLIO_REPOS:
        print(f"  [REPO]  Fetching {repo_name}...")
        r    = client.repo(repo_name)
        langs = client.languages(repo_name)
        repo_data[repo_name] = {
            "name":        r.get("name", repo_name),
            "description": r.get("description", ""),
            "stars":       r.get("stargazers_count", 0),
            "forks":       r.get("forks_count", 0),
            "watchers":    r.get("watchers_count", 0),
            "language":    r.get("language", "Python"),
            "languages":   list(langs.keys())[:4] if langs else ["Python"],
            "updated_at":  r.get("updated_at", ""),
            "url":         r.get("html_url", f"https://github.com/{USERNAME}/{repo_name}"),
            "topics":      r.get("topics", []),
            "size":        r.get("size", 0),
        }
        s = repo_data[repo_name]["stars"]
        f = repo_data[repo_name]["forks"]
        print(f"    ✓ ★{s} ⑂{f} — {repo_data[repo_name]['language']}")

    return {
        "username":     client.username,
        "name":         user.get("name", USERNAME),
        "bio":          user.get("bio", ""),
        "avatar":       user.get("avatar_url", ""),
        "followers":    user.get("followers", 0),
        "following":    user.get("following", 0),
        "public_repos": user.get("public_repos", len(all_repos)),
        "total_stars":  total_stars,
        "total_forks":  total_forks,
        "repos":        repo_data,
        "fetched_at":   datetime.now().isoformat(),
    }


# ── Inject data into HTML ─────────────────────────────────────
def bake_html(data: dict) -> str:
    """Read template HTML and bake in live GitHub data."""
    html = TEMPLATE_PATH.read_text(encoding="utf-8")

    # ── Patch stat numbers ────────────────────────────────────
    # These replace the JS fetch — makes the page work offline too
    html = re.sub(
        r'(<span class="stat-num" id="statRepos">)[^<]*(</span>)',
        rf'\g<1>{data["public_repos"]}\g<2>', html
    )
    html = re.sub(
        r'(<span class="stat-num" id="statStars">)[^<]*(</span>)',
        rf'\g<1>{data["total_stars"]}\g<2>', html
    )

    # ── Patch project stars/forks in the JS data ─────────────
    for repo_name, repo in data["repos"].items():
        # Replace "—" placeholders in JS PROJECTS array
        # Match stars line for this repo's key
        pattern = rf'(repoKey:\s*"{re.escape(repo_name)}"[^}}]*?stars:\s*")[^"]*(")'
        html = re.sub(pattern, rf'\g<1>{repo["stars"]}\g<2>', html, flags=re.DOTALL)
        pattern2 = rf'(repoKey:\s*"{re.escape(repo_name)}"[^}}]*?forks:\s*")[^"]*(")'
        html = re.sub(pattern2, rf'\g<1>{repo["forks"]}\g<2>', html, flags=re.DOTALL)

    # ── Inject build timestamp in footer ─────────────────────
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = re.sub(
        r'(B\.Tech AI[^<]*</span>)',
        rf'B.Tech AI &amp; ML, VIT Chennai · Built {ts}</span>',
        html
    )

    # ── Inject data payload for JS (optional enhancement) ────
    payload = f"\n<script>window.__GITHUB_DATA__ = {json.dumps(data, indent=2)};</script>\n"
    html = html.replace("</body>", payload + "</body>")

    return html


# ── Summary report ────────────────────────────────────────────
def print_summary(data: dict):
    print(f"\n  {'─'*52}")
    print(f"  PORTFOLIO DATA SUMMARY")
    print(f"  {'─'*52}")
    print(f"  GitHub user   : @{data['username']}")
    print(f"  Public repos  : {data['public_repos']}")
    print(f"  Total stars   : {data['total_stars']}")
    print(f"  Total forks   : {data['total_forks']}")
    print(f"  {'─'*52}")
    print(f"  {'Repo':<35} {'Stars':>5} {'Forks':>5}")
    print(f"  {'─'*52}")
    for name, repo in data["repos"].items():
        print(f"  {name:<35} {repo['stars']:>5} {repo['forks']:>5}")
    print(f"  {'─'*52}")
    print(f"  Fetched at: {data['fetched_at']}")


# ── Main ──────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="GitHub Portfolio Data Baker")
    parser.add_argument("--username", default=USERNAME)
    parser.add_argument("--token",    default=None,
                        help="GitHub personal access token (increases rate limit to 5000/hr)")
    parser.add_argument("--dry-run",  action="store_true",
                        help="Fetch data but don't write HTML")
    args = parser.parse_args()

    print(f"\n{'='*56}")
    print(f"  PORTFOLIO BUILDER")
    print(f"  GitHub: @{args.username}")
    print(f"  Time:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*56}")

    client = GitHubClient(args.username, args.token)
    data   = fetch_portfolio_data(client)

    print_summary(data)

    if not args.dry_run:
        print(f"\n  Building portfolio HTML...")
        html = bake_html(data)
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(html, encoding="utf-8")
        size_kb = OUTPUT_PATH.stat().st_size / 1024
        print(f"  ✅  Written → {OUTPUT_PATH}  ({size_kb:.1f} KB)")
        print(f"\n  Open in browser:")
        print(f"  → file://{OUTPUT_PATH.resolve()}")
        print(f"\n  Deploy to GitHub Pages:")
        print(f"  → Push to github.com/{args.username}/{args.username}.github.io")
        print(f"     or use GitHub Pages on any repo's /docs folder")
    else:
        print(f"\n  [DRY RUN] Data fetched. HTML not written.")

    print(f"\n{'='*56}\n")


if __name__ == "__main__":
    main()
