import json
import math
import os
import re
import sys
import textwrap
import urllib.request
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

USER = os.environ.get("GITHUB_USER", "darleenfritz")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
README = ROOT / "README.md"
CONFIG = ROOT / "projects.json"
PORTFOLIO_TOPIC = "portfolio"

BG = "#FBEAF0"
BORDER = "#F4C0D1"
TITLE = "#72243E"
TEXT = "#993556"
ACCENT = "#D4537E"
GOLD = "#C9A35E"
SHADES = ["#72243E", "#993556", "#D4537E", "#ED93B1", "#F4C0D1"]
CHARMS = ["#D4537E", "#993556", "#B04A6E", "#72243E", "#C2577F", "#A63D63"]
FONT = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
SERIF = "Georgia, 'Times New Roman', serif"

TOPIC_NAMES = {
    "javascript": "JavaScript", "typescript": "TypeScript", "php": "PHP", "mysql": "MySQL",
    "openai": "OpenAI", "rest-api": "REST API", "react-native": "React Native", "jwt": "JWT",
    "html": "HTML", "css": "CSS", "macos": "macOS", "ios": "iOS", "api": "API", "ai": "AI",
}


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


def load_config():
    if CONFIG.exists():
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    return {}


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
            f'<circle cx="34" cy="{y - 6}" r="5" fill="{ACCENT}"/>'
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


def topic_name(topic):
    if topic in TOPIC_NAMES:
        return TOPIC_NAMES[topic]
    return " ".join(w.capitalize() for w in topic.split("-"))


def portfolio_projects(repos, config):
    names = config.get("names", {})
    order = config.get("order", [])
    projects = []
    for r in repos:
        topics = r.get("topics") or []
        if PORTFOLIO_TOPIC not in topics:
            continue
        title = names.get(r["name"]) or " ".join(w.capitalize() for w in r["name"].split("-"))
        tags = [topic_name(t) for t in topics if t != PORTFOLIO_TOPIC][:3]
        projects.append({
            "slug": r["name"],
            "title": title,
            "description": r.get("description") or "",
            "tags": tags,
            "url": r["html_url"],
            "created": r.get("created_at") or "",
        })
    rank = {slug: i for i, slug in enumerate(order)}
    projects.sort(key=lambda p: (rank.get(p["slug"], len(rank)), p["created"]))
    return projects


def bracelet(projects):
    n = len(projects)
    cx, cy, r = 200, 200, 104
    hold, move = 3.2, 0.9
    period = n * (hold + move)
    seg = 100 / n
    held = seg * hold / (hold + move)
    ring = ""
    counter = ""
    for k in range(n):
        angle = k * 360 / n
        ring += f"{k * seg:.3f}%,{k * seg + held:.3f}%{{transform:rotate({-angle:.3f}deg)}}"
        counter += f"{k * seg:.3f}%,{k * seg + held:.3f}%{{transform:rotate({angle:.3f}deg)}}"
    ring += "100%{transform:rotate(-360deg)}"
    counter += "100%{transform:rotate(360deg)}"
    fade = 1.2
    panel = f"0%{{opacity:0}}{fade:.2f}%{{opacity:1}}{held - fade:.2f}%{{opacity:1}}{held:.2f}%,100%{{opacity:0}}"
    if n == 1:
        ring, counter = "0%,100%{transform:none}", "0%,100%{transform:none}"
        panel = "0%,100%{opacity:1}"
    css = (
        f".ring{{transform-box:view-box;transform-origin:{cx}px {cy}px;animation:ring {period:.1f}s cubic-bezier(.6,0,.3,1) infinite}}"
        f".charm{{transform-box:fill-box;transform-origin:center;animation:counter {period:.1f}s cubic-bezier(.6,0,.3,1) infinite}}"
        f".panel{{opacity:0;animation:panel {period:.1f}s linear infinite}}"
        ".glow{animation:glow 2.4s ease-in-out infinite}"
        f"@keyframes ring{{{ring}}}@keyframes counter{{{counter}}}@keyframes panel{{{panel}}}"
        "@keyframes glow{0%,100%{opacity:.35}50%{opacity:.8}}"
        "@media (prefers-reduced-motion:reduce){.ring,.charm,.glow{animation:none}.panel{animation:none;opacity:0}.p0{opacity:1}}"
    )
    links = ""
    for i in range(48):
        a = i * 360 / 48
        x = cx + r * math.cos(math.radians(a))
        y = cy + r * math.sin(math.radians(a))
        links += f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="7" ry="4" transform="rotate({a + 90:.1f} {x:.1f} {y:.1f})" fill="none" stroke="{GOLD}" stroke-width="2.2"/>'
    charms = ""
    panels = ""
    for i, p in enumerate(projects):
        a = -90 + i * 360 / n
        x = cx + (r + 34) * math.cos(math.radians(a))
        y = cy + (r + 34) * math.sin(math.radians(a))
        jx = cx + (r + 6) * math.cos(math.radians(a))
        jy = cy + (r + 6) * math.sin(math.radians(a))
        charms += (
            f'<line x1="{jx:.1f}" y1="{jy:.1f}" x2="{x:.1f}" y2="{y:.1f}" stroke="{GOLD}" stroke-width="2.5"/>'
            f'<g class="charm"><circle cx="{x:.1f}" cy="{y:.1f}" r="27" fill="{CHARMS[i % len(CHARMS)]}" stroke="{GOLD}" stroke-width="3"/>'
            f'<circle cx="{x - 9:.1f}" cy="{y - 10:.1f}" r="5" fill="#FFFFFF" opacity=".35"/>'
            f'<text x="{x:.1f}" y="{y + 10:.1f}" text-anchor="middle" font-family="{SERIF}" font-style="italic" font-size="27" fill="{BG}">{escape(p["title"][0])}</text></g>'
        )
        lines = textwrap.wrap(p["description"], 46)[:2]
        desc = "".join(
            f'<text x="400" y="{222 + j * 24}" font-family="{FONT}" font-size="17" fill="{TEXT}">{escape(line)}</text>'
            for j, line in enumerate(lines)
        )
        pills = ""
        px = 400
        py = 222 + len(lines) * 24
        for tag in p["tags"]:
            w = len(tag) * 8 + 24
            pills += (
                f'<rect x="{px}" y="{py}" width="{w:.0f}" height="28" rx="14" fill="{BORDER}"/>'
                f'<text x="{px + w / 2:.0f}" y="{py + 19}" text-anchor="middle" font-family="{FONT}" font-size="14" fill="{TITLE}">{escape(tag)}</text>'
            )
            px += w + 10
        panels += (
            f'<g class="panel p{i}" style="animation-delay:{i * period / n:.2f}s">'
            f'<text x="400" y="150" font-family="{FONT}" font-size="14" letter-spacing="2" fill="{ACCENT}">PROJECT {i + 1} OF {n}</text>'
            f'<text x="400" y="190" font-family="{SERIF}" font-size="36" fill="{TITLE}">{escape(p["title"])}</text>'
            f"{desc}{pills}</g>"
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="380" viewBox="0 0 900 380" role="img" aria-label="My projects as a charm bracelet">'
        f"<style>{css}</style>"
        f'<rect x="0.5" y="0.5" width="899" height="379" rx="20" fill="{BG}" stroke="{BORDER}"/>'
        f'<circle class="glow" cx="{cx}" cy="{cy - r - 34}" r="38" fill="{BORDER}"/>'
        f'<g class="ring">{links}{charms}</g>'
        f'<path d="M{cx - 9} 10 L{cx + 9} 10 L{cx} 22 Z" fill="{GOLD}"/>'
        f'<text x="{cx}" y="{cy + 6}" text-anchor="middle" font-family="{SERIF}" font-style="italic" font-size="22" fill="{TEXT}">my projects</text>'
        f"{panels}</svg>\n"
    )


def projects_markdown(projects):
    if not projects:
        return "<!-- PROJECTS:START -->\n<!-- PROJECTS:END -->"
    links = " · ".join(f'<a href="{p["url"]}">{escape(p["title"])}</a>' for p in projects)
    return (
        "<!-- PROJECTS:START -->\n"
        '<p align="center">\n'
        '  <img src="assets/projects.svg" alt="My projects as a rotating charm bracelet" width="100%">\n'
        "</p>\n\n"
        f'<p align="center">\n  {links}\n</p>\n'
        "<!-- PROJECTS:END -->"
    )


def update_readme(projects):
    text = README.read_text(encoding="utf-8")
    pattern = re.compile(r"<!-- PROJECTS:START -->.*?<!-- PROJECTS:END -->", re.S)
    if not pattern.search(text):
        return
    README.write_text(pattern.sub(lambda _: projects_markdown(projects), text), encoding="utf-8")


def main():
    OUT.mkdir(exist_ok=True)
    repos = own_repos()
    projects = portfolio_projects(repos, load_config())
    (OUT / "stats.svg").write_text(stats_card(repos, contributions_this_year()), encoding="utf-8")
    (OUT / "languages.svg").write_text(languages_card(repos), encoding="utf-8")
    if projects:
        (OUT / "projects.svg").write_text(bracelet(projects), encoding="utf-8")
        update_readme(projects)
    print(f"{len(repos)} repositories, {len(projects)} portfolio projects")


if __name__ == "__main__":
    sys.exit(main())
