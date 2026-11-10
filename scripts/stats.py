import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

USER = os.environ.get("GITHUB_USER", "darleenfritz")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = Path(__file__).resolve().parent.parent / "assets"

BG = "#FBEAF0"
BORDER = "#F4C0D1"
TITLE = "#72243E"
TEXT = "#993556"
SHADES = ["#72243E", "#993556", "#D4537E", "#ED93B1", "#F4C0D1"]
FONT = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
SERIF = "Georgia, 'Times New Roman', serif"


def request(url, data=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if data is not None:
        data = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read())


def own_repos():
    repos = request(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner")
    return [r for r in repos if not r["fork"] and r["name"].lower() != USER.lower()]


def contributions_this_year():
    if not TOKEN:
        return None
    start = f"{date.today().year}-01-01T00:00:00Z"
    query = {
        "query": "query($login:String!,$from:DateTime!){user(login:$login){contributionsCollection(from:$from){contributionCalendar{totalContributions}}}}",
        "variables": {"login": USER, "from": start},
    }
    try:
        result = request("https://api.github.com/graphql", query)
        return result["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    except Exception:
        return None


def card(width, height, title, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">'
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="16" fill="{BG}" stroke="{BORDER}"/>'
        f'<text x="28" y="44" font-family="{SERIF}" font-size="22" fill="{TITLE}">{escape(title)}</text>'
        f"{body}</svg>\n"
    )


def stats_card(repos, contributions):
    rows = [
        ("Public projects", len(repos)),
        ("Stars earned", sum(r["stargazers_count"] for r in repos)),
    ]
    if contributions is not None:
        rows.append((f"Contributions in {date.today().year}", contributions))
    body = ""
    for i, (label, value) in enumerate(rows):
        y = 92 + i * 38
        body += (
            f'<circle cx="34" cy="{y - 6}" r="5" fill="{SHADES[2]}"/>'
            f'<text x="50" y="{y}" font-family="{FONT}" font-size="16" fill="{TEXT}">{escape(label)}</text>'
            f'<text x="467" y="{y}" text-anchor="end" font-family="{FONT}" font-size="18" font-weight="600" fill="{TITLE}">{value}</text>'
        )
    return card(495, 195, "My GitHub", body)


def languages_card(repos):
    totals = {}
    for r in repos:
        for lang, size in request(r["languages_url"]).items():
            totals[lang] = totals.get(lang, 0) + size
    top = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:5]
    total = sum(v for _, v in top) or 1
    body = ""
    x = 28.0
    bar_width = 439
    for i, (_, size) in enumerate(top):
        w = bar_width * size / total
        body += f'<rect x="{x:.1f}" y="66" width="{w:.1f}" height="12" fill="{SHADES[i]}"/>'
        x += w
    body = f'<clipPath id="bar"><rect x="28" y="66" width="{bar_width}" height="12" rx="6"/></clipPath><g clip-path="url(#bar)">{body}</g>'
    for i, (lang, size) in enumerate(top):
        col, row = i % 2, i // 2
        cx = 34 + col * 225
        cy = 112 + row * 30
        pct = round(100 * size / total)
        body += (
            f'<circle cx="{cx}" cy="{cy - 5}" r="6" fill="{SHADES[i]}" stroke="{TEXT}" stroke-width="0.5"/>'
            f'<text x="{cx + 14}" y="{cy}" font-family="{FONT}" font-size="15" fill="{TEXT}">{escape(lang)} <tspan fill="{TITLE}" font-weight="600">{pct} %</tspan></text>'
        )
    return card(495, 195, "Top languages", body)


def main():
    OUT.mkdir(exist_ok=True)
    repos = own_repos()
    (OUT / "stats.svg").write_text(stats_card(repos, contributions_this_year()), encoding="utf-8")
    (OUT / "languages.svg").write_text(languages_card(repos), encoding="utf-8")
    print(f"{len(repos)} repositories processed")


if __name__ == "__main__":
    sys.exit(main())
