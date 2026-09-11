#!/usr/bin/env python3
"""
generate_stats.py — builds custom GitHub Stats SVGs into assets/.
Runs locally (with a PAT) and in GitHub Actions (with GITHUB_TOKEN).
Never fails the build: on API errors it keeps the previous SVGs.
"""
import json
import os
import urllib.request
from datetime import datetime, timezone

USER = os.environ.get("GH_USERNAME", "b2kproedit")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.path.join(os.path.dirname(__file__), "..", "assets")

HDRS = {"Authorization": f"token {TOKEN}", "User-Agent": "stats-bot",
        "Accept": "application/vnd.github+json"}
GQL = {"Authorization": f"bearer {TOKEN}", "User-Agent": "stats-bot",
       "Content-Type": "application/json"}

LANG_COLORS = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Python": "#3572A5",
    "Rust": "#dea584", "Go": "#00ADD8", "HTML": "#e34c26", "CSS": "#563d7c",
    "Java": "#b07219", "C++": "#f34b7d", "C": "#555555", "Shell": "#89e051",
    "Dart": "#00B4AB", "Kotlin": "#A97BFF", "Ruby": "#701516", "PHP": "#4F5D95",
    "Jupyter Notebook": "#DA5B0B", "Vue": "#41b883", "SCSS": "#c6538c",
}
FALLBACK_COLORS = ["#7C5CFF", "#00D4FF", "#FF5E78", "#2ECC71", "#F5C518", "#5B8CFF"]


def gql(query, variables=None):
    req = urllib.request.Request("https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers=GQL)
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def rest(path):
    req = urllib.request.Request(f"https://api.github.com{path}", headers=HDRS)
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fetch():
    res = gql("""
    query($u:String!){
      user(login:$u){
        followers{ totalCount }
        repositories(first:100, ownerAffiliations:OWNER){
          totalCount
          nodes{ name stargazerCount forkCount }
        }
        contributionsCollection{ totalCommitContributions }
        issues{ totalCount }
        pullRequests{ totalCount }
      }
    }""", {"u": USER})
    d = res["data"]["user"]
    repos = d["repositories"]["nodes"]

    langs = {}
    for r in repos:
        try:
            for name, b in rest(f"/repos/{USER}/{r['name']}/languages").items():
                langs[name] = langs.get(name, 0) + b
        except Exception:
            pass

    total_bytes = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda x: -x[1])[:6]
    langs_out = []
    for i, (name, b) in enumerate(top):
        langs_out.append({
            "name": name,
            "pct": round(b * 100 / total_bytes, 1),
            "color": LANG_COLORS.get(name, FALLBACK_COLORS[i % len(FALLBACK_COLORS)]),
        })

    return {
        "followers": d["followers"]["totalCount"],
        "repos": d["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "forks": sum(r["forkCount"] for r in repos),
        "commits": d["contributionsCollection"]["totalCommitContributions"],
        "issues": d["issues"]["totalCount"],
        "prs": d["pullRequests"]["totalCount"],
        "langs": langs_out,
        "generated": datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC"),
    }


FONT = "Segoe UI,Helvetica Neue,Arial,sans-serif"


def stats_svg(d):
    metrics = [
        ("Total Stars", d["stars"], "#F5C518"),
        ("Total Repos", d["repos"], "#7C5CFF"),
        ("Commits (1yr)", d["commits"], "#00D4FF"),
        ("Total Forks", d["forks"], "#5B8CFF"),
        ("Followers", d["followers"], "#2ECC71"),
        ("Issues & PRs", d["issues"] + d["prs"], "#FF5E78"),
    ]
    cols = [24, 188, 352]
    rows = [(70, 100), (136, 166)]

    cells = ""
    for i, (label, value, color) in enumerate(metrics):
        x = cols[i % 3]
        ly, vy = rows[i // 3]
        cells += f'''
  <rect x="{x}" y="{ly - 14}" width="4" height="42" rx="2" fill="{color}" opacity="0.9"/>
  <text x="{x + 14}" y="{ly + 2}" font-family="{FONT}" font-size="11" font-weight="600" fill="#8B949E" letter-spacing="0.5">{esc(label.upper())}</text>
  <text x="{x + 14}" y="{vy + 4}" font-family="{FONT}" font-size="26" font-weight="800" fill="#FFFFFF">{value:,}</text>'''

    return f'''<svg width="495" height="195" viewBox="0 0 495 195" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="GitHub Stats">
  <defs>
    <linearGradient id="tg" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#7C5CFF"/><stop offset="100%" stop-color="#00D4FF"/>
    </linearGradient>
    <linearGradient id="bg1" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#7C5CFF"/><stop offset="100%" stop-color="#00D4FF"/>
    </linearGradient>
  </defs>
  <rect x="1" y="1" width="493" height="193" rx="12" fill="#0D1117" stroke="url(#bg1)" stroke-opacity="0.35" stroke-width="1.5"/>
  <text x="24" y="38" font-family="{FONT}" font-size="18" font-weight="800" fill="url(#tg)">⚡ {esc(USER)}'s GitHub Stats</text>{cells}
  <text x="471" y="184" text-anchor="end" font-family="{FONT}" font-size="8" fill="#8B949E" opacity="0.7">auto-updated {d["generated"]}</text>
</svg>'''


def langs_svg(d):
    langs = d["langs"]
    if not langs:
        langs = [{"name": "n/a", "pct": 100, "color": "#7C5CFF"}]

    bar_x, bar_w, bar_y, bar_h = 24, 447, 62, 14
    segs, cursor = "", 0.0
    clip_id = "barclip"
    for l in langs:
        w = bar_w * l["pct"] / sum(x["pct"] for x in langs)
        segs += f'<rect x="{bar_x + cursor:.1f}" y="{bar_y}" width="{w:.1f}" height="{bar_h}" fill="{l["color"]}"/>'
        cursor += w

    legend = ""
    cols = [24, 252]
    for i, l in enumerate(langs):
        x = cols[i % 2]
        y = 106 + (i // 2) * 30
        legend += f'''
  <circle cx="{x + 6}" cy="{y - 4}" r="5" fill="{l["color"]}"/>
  <text x="{x + 20}" y="{y}" font-family="{FONT}" font-size="13" font-weight="600" fill="#FFFFFF">{esc(l["name"])}</text>
  <text x="{x + 200}" y="{y}" font-family="{FONT}" font-size="12" fill="#8B949E">{l["pct"]}%</text>'''

    return f'''<svg width="495" height="195" viewBox="0 0 495 195" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Most Used Languages">
  <defs>
    <linearGradient id="tg2" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#7C5CFF"/><stop offset="100%" stop-color="#00D4FF"/>
    </linearGradient>
    <clipPath id="{clip_id}"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="7"/></clipPath>
  </defs>
  <rect x="1" y="1" width="493" height="193" rx="12" fill="#0D1117" stroke="#7C5CFF" stroke-opacity="0.35" stroke-width="1.5"/>
  <text x="24" y="38" font-family="{FONT}" font-size="18" font-weight="800" fill="url(#tg2)">📊 Most Used Languages</text>
  <g clip-path="url(#{clip_id})">{segs}</g>{legend}
  <text x="471" y="184" text-anchor="end" font-family="{FONT}" font-size="8" fill="#8B949E" opacity="0.7">by bytes of code • auto-updated</text>
</svg>'''


def main():
    try:
        data = fetch()
    except Exception as e:
        print(f"⚠️ API error — keeping previous SVGs: {e}")
        return

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "github-stats-card.svg"), "w") as f:
        f.write(stats_svg(data))
    with open(os.path.join(OUT, "github-langs-card.svg"), "w") as f:
        f.write(langs_svg(data))
    print(f"✅ SVGs generated — stars:{data['stars']} repos:{data['repos']} commits:{data['commits']}")


if __name__ == "__main__":
    main()
