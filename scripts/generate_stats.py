#!/usr/bin/env python3
"""Draw four contribution graphics from the GitHub GraphQL API.

Standard library only -- urllib for the API, nothing to break in CI.

    GITHUB_TOKEN=... GH_LOGIN=mustafa3252 python3 scripts/generate_stats.py

Two determinism traps are handled here, and both matter. Miss either and the
scheduled job produces a nightly stream of meaningless commits:

  1. The contribution window is pinned to whole UTC days. Left alone,
     contributionsCollection measures "the past year" from the moment of the
     request, so two runs minutes apart bucket days into different weeks and
     shift the sparkline by a fraction of a pixel.

  2. Repositories are filtered to public only. A personal token sees private
     repos; the workflow's GITHUB_TOKEN does not. Without the filter, language
     percentages disagree depending on who ran the script.
"""
import bisect
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from svgkit import ROOT, STACK, THEMES, esc, font_face  # noqa: E402

API = "https://api.github.com/graphql"
RAMP = " .`:-=+*cs#%@"

USER_Q = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    name login createdAt
    followers { totalCount }
    contributionsCollection(from:$from, to:$to) {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

REPO_Q = """
query($login:String!, $cursor:String) {
  user(login:$login) {
    repositories(first:100, privacy:PUBLIC, ownerAffiliations:OWNER,
                 isFork:false, after:$cursor) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        name stargazerCount forkCount
        primaryLanguage { name }
        languages(first:12, orderBy:{field:SIZE, direction:DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
def query(token: str, doc: str, variables: dict):
    # variables is a dict rather than **kwargs because GraphQL's $from
    # collides with a Python keyword.
    body = json.dumps({"query": doc, "variables": variables}).encode()
    req = urllib.request.Request(
        API,
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-readme-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise RuntimeError(json.dumps(payload["errors"], indent=2))
    return payload["data"]


def fetch(token: str, login: str) -> dict:
    # Trap 1: pin the window to whole UTC days so the buckets never move.
    today = dt.datetime.now(dt.timezone.utc).date()
    start = today - dt.timedelta(days=364)
    frm = f"{start.isoformat()}T00:00:00Z"
    to = f"{today.isoformat()}T23:59:59Z"

    user = query(token, USER_Q, {"login": login, "from": frm, "to": to})["user"]

    repos, cursor = [], None
    while True:
        page = query(token, REPO_Q, {"login": login, "cursor": cursor})["user"]["repositories"]
        repos.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    return {"user": user, "repos": repos, "window": (start, today)}


# --------------------------------------------------------------------------
# Shaping
# --------------------------------------------------------------------------
def calendar_days(user: dict) -> list[tuple[dt.date, int]]:
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [
        (dt.date.fromisoformat(d["date"]), d["contributionCount"])
        for w in weeks
        for d in w["contributionDays"]
    ]


def streaks(days: list[tuple[dt.date, int]]) -> dict:
    """Current and longest run of consecutive active days.

    Only the last 365 days are in the calendar, so both are in-window figures
    and the graphic says so rather than implying all-time.
    """
    best = cur = 0
    best_end = cur_start = None
    for date, count in days:
        if count:
            cur = cur + 1 if cur else 1
            if cur == 1:
                cur_start = date
            if cur > best:
                best, best_end = cur, date
        else:
            cur, cur_start = 0, None

    # A day with no contributions yet does not break a live streak until it
    # ends, so fall back to the run that finished yesterday.
    trailing, t_start = cur, cur_start
    if not trailing and len(days) > 1:
        run, start = 0, None
        for date, count in days[:-1]:
            if count:
                run = run + 1 if run else 1
                if run == 1:
                    start = date
            else:
                run, start = 0, None
        trailing, t_start = run, start

    return {
        "current": trailing,
        "current_from": t_start,
        "current_to": days[-1][0] if trailing else None,
        "longest": best,
        "longest_to": best_end,
        "longest_from": best_end - dt.timedelta(days=best - 1) if best else None,
    }


def language_totals(repos: list[dict]) -> tuple[list, list]:
    by_bytes: dict[str, int] = {}
    by_repo: dict[str, int] = {}
    for r in repos:
        for edge in r["languages"]["edges"]:
            by_bytes[edge["node"]["name"]] = (
                by_bytes.get(edge["node"]["name"], 0) + edge["size"]
            )
        primary = r.get("primaryLanguage")
        if primary:
            by_repo[primary["name"]] = by_repo.get(primary["name"], 0) + 1
    rank = lambda d: sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))
    return rank(by_bytes), rank(by_repo)


def compact(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 10_000:
        return f"{n // 1000}k"
    if n >= 1_000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return str(n)


# --------------------------------------------------------------------------
# Drawing
# --------------------------------------------------------------------------
def head(w: int, h: int, pal: dict, label: str, *, subsets=("ui", "ui-bold")) -> list[str]:
    faces = "".join(
        font_face("JBMono", s, 700 if s.endswith("bold") else 400) for s in subsets
    )
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="{esc(label)}">',
        f"<defs><style>{faces}"
        f"text{{font-family:{STACK};fill:{pal['ink']};}}"
        f".l{{font-size:10px;fill:{pal['dim']};letter-spacing:.14em;}}"
        f".k{{font-size:9.5px;fill:{pal['dim']};letter-spacing:.1em;}}"
        f".v{{font-size:12.5px;}}"
        f".big{{font-size:38px;font-weight:700;letter-spacing:-.02em;}}"
        f".mid{{font-size:21px;font-weight:700;}}"
        "</style></defs>",
    ]


def rule(x: float, y: float, w: float, pal: dict) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="1" fill="{pal["rule"]}"/>'


def card_label(text: str, x: float, y: float, w: float, pal: dict) -> str:
    """Lowercase mono label with a hairline rule running to the right edge."""
    tw = len(text) * 6.6 + 10
    return (
        f'<text class="l" x="{x}" y="{y}">{esc(text)}</text>'
        + rule(x + tw, y - 4, max(0, w - tw - x * 2 + x), pal)
    )


def draw_stats(data: dict, pal: dict) -> str:
    W, H, P = 430, 172, 18
    user = data["user"]
    cc = user["contributionsCollection"]
    days = calendar_days(user)
    total = cc["contributionCalendar"]["totalContributions"]
    active = sum(1 for _, c in days if c)

    out = head(W, H, pal, f"{total} contributions in the last year")
    out.append(card_label("contributions", P, 22, W - P, pal))

    out.append(f'<text class="big" x="{P}" y="{62}">{total:,}</text>')
    out.append(
        f'<text class="k" x="{P}" y="{80}">'
        f"PAST 365 DAYS &#183; {active} ACTIVE</text>"
    )

    # Breakdown, right-aligned so the hero number owns the left edge.
    rows = [
        ("commits", cc["totalCommitContributions"]),
        ("pull requests", cc["totalPullRequestContributions"]),
        ("reviews", cc["totalPullRequestReviewContributions"]),
        ("issues", cc["totalIssueContributions"]),
    ]
    for i, (name, val) in enumerate(rows):
        y = 36 + i * 15
        out.append(f'<text class="k" x="{W - P - 44}" y="{y}" text-anchor="end">{name.upper()}</text>')
        out.append(f'<text class="v" x="{W - P}" y="{y}" text-anchor="end">{val:,}</text>')

    # Weekly aggregate, drawn as an area. A line over *daily* counts would be
    # dishonest -- it claims values between two zero days that never existed --
    # but weekly totals are continuous enough for the interpolation to mean
    # something.
    weeks = [
        sum(c for _, c in days[i:i + 7]) for i in range(0, len(days) - 6, 7)
    ]
    gx, gy, gw, gh = P, 96, W - P * 2, 52
    peak = max(weeks) or 1
    step = gw / max(1, len(weeks) - 1)
    pts = [
        (gx + i * step, gy + gh - (v / peak) * gh)
        for i, v in enumerate(weeks)
    ]
    line = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
    out.append(
        f'<path d="{line} L{pts[-1][0]:.1f},{gy + gh} L{gx},{gy + gh} Z" '
        f'fill="{pal["accent"]}" opacity="0.13"/>'
    )
    out.append(f'<path d="{line}" fill="none" stroke="{pal["accent"]}" '
               f'stroke-width="1.6" stroke-linejoin="round"/>')
    out.append(rule(gx, gy + gh, gw, pal))
    out.append(f'<text class="k" x="{gx}" y="{H - 8}">WEEKLY &#183; PEAK {peak}</text>')
    out.append(f'<text class="k" x="{gx + gw}" y="{H - 8}" text-anchor="end">'
               f"{len(weeks)} WEEKS</text>")
    out.append("</svg>")
    return "".join(out)


def draw_streak(data: dict, pal: dict) -> str:
    W, H, P = 430, 172, 18
    days = calendar_days(data["user"])
    s = streaks(days)
    repos = data["repos"]

    fmt = lambda d: d.strftime("%d %b %Y").lstrip("0") if d else "--"

    out = head(W, H, pal, f"current streak {s['current']} days")
    out.append(card_label("streak", P, 22, W - P, pal))

    blocks = [
        ("CURRENT", s["current"], s["current_from"], s["current_to"]),
        ("LONGEST", s["longest"], s["longest_from"], s["longest_to"]),
    ]
    for i, (name, val, a, b) in enumerate(blocks):
        x = P + i * (W - P * 2) / 2
        out.append(f'<text class="k" x="{x}" y="{46}">{name}</text>')
        out.append(f'<text class="mid" x="{x}" y="{70}">{val}'
                   f'<tspan class="k" dx="5">DAY{"" if val == 1 else "S"}</tspan></text>')
        out.append(f'<text class="k" x="{x}" y="{88}">{fmt(a)} &#8594; {fmt(b)}</text>')

    out.append(rule(P, 104, W - P * 2, pal))

    footer = [
        ("repositories", len(repos)),
        ("stars", sum(r["stargazerCount"] for r in repos)),
        ("forks", sum(r["forkCount"] for r in repos)),
        ("followers", data["user"]["followers"]["totalCount"]),
    ]
    for i, (name, val) in enumerate(footer):
        x = P + i * (W - P * 2) / 4
        out.append(f'<text class="k" x="{x}" y="{128}">{name.upper()}</text>')
        out.append(f'<text class="mid" x="{x}" y="{152}">{compact(val)}</text>')

    out.append(f'<text class="k" x="{P}" y="{H - 6}">'
               f"WITHIN THE PAST 365 DAYS &#183; PUBLIC ACTIVITY</text>")
    out.append("</svg>")
    return "".join(out)


def draw_langs(data: dict, pal: dict) -> str:
    W, H, P = 880, 236, 20
    by_bytes, by_repo = language_totals(data["repos"])
    out = head(W, H, pal, "top languages")
    out.append(card_label("languages", P, 24, W - P, pal))

    col_w = (W - P * 2 - 40) / 2
    GUTTER = 100          # room for the right-aligned value, clear of the bar
    panels = [
        ("BY BYTES OF CODE", by_bytes[:6], lambda v: f"{v / 1_048_576:.1f} MB", P),
        ("BY REPOSITORIES", by_repo[:6], lambda v: f"{v} repo{'' if v == 1 else 's'}",
         P + col_w + 40),
    ]

    for title, rows, label, x in panels:
        out.append(f'<text class="k" x="{x}" y="{50}">{title}</text>')
        peak = max((v for _, v in rows), default=1) or 1
        total = sum(v for _, v in rows) or 1
        for i, (name, val) in enumerate(rows):
            y = 68 + i * 22
            bar_x = x + 96
            track = col_w - 96 - GUTTER
            bar_w = track * (val / peak)
            # One hue, stepped by opacity. Per-item colouring is what makes a
            # generated graphic read as noise rather than as a designed thing.
            op = 0.92 - i * 0.115
            out.append(f'<text class="v" x="{x}" y="{y + 9}">{esc(name)}</text>')
            out.append(f'<rect x="{bar_x}" y="{y}" width="{track:.1f}" '
                       f'height="10" fill="{pal["faint"]}" rx="1"/>')
            out.append(f'<rect x="{bar_x}" y="{y}" width="{max(1.5, bar_w):.1f}" '
                       f'height="10" fill="{pal["accent"]}" opacity="{op:.2f}" rx="1"/>')
            out.append(f'<text class="k" x="{x + col_w}" y="{y + 9}" '
                       f'text-anchor="end">{label(val)} &#183; {val / total * 100:.0f}%</text>')

    out.append(rule(P, H - 26, W - P * 2, pal))
    out.append(f'<text class="k" x="{P}" y="{H - 10}">'
               f"{len(data['repos'])} PUBLIC SOURCE REPOSITORIES &#183; FORKS EXCLUDED</text>")
    out.append("</svg>")
    return "".join(out)


def draw_year(data: dict, pal: dict) -> str:
    """The year at one character per day, drawn with the portrait's own ramp."""
    W, H, P = 880, 284, 20
    days = calendar_days(data["user"])
    counts = dict(days)

    FS = 19.5
    CW = FS * 0.6                 # 0.600 em, the same grid the portrait uses
    LH = CW / 0.48
    LEFT = P + 44

    # Columns are ISO-style weeks starting Sunday, matching GitHub's own graph.
    first = days[0][0]
    origin = first - dt.timedelta(days=(first.weekday() + 1) % 7)
    cells: dict[tuple[int, int], tuple[dt.date, int]] = {}
    for date, count in days:
        col = (date - origin).days // 7
        row = (date.weekday() + 1) % 7
        cells[(row, col)] = (date, count)
    ncols = max(c for _, c in cells) + 1

    # Rank-based levels, not linear ones. A handful of 80-contribution days
    # would otherwise flatten every ordinary day onto the same ramp step.
    active = sorted(c for _, c in days if c)
    steps = len(RAMP) - 1

    def level(count: int) -> int:
        if not count or not active:
            return 0
        rank = bisect.bisect_left(active, count) / len(active)
        return max(1, min(steps, 1 + int(rank * (steps - 1) + 0.5)))

    out = head(W, H, pal, "contributions for each day of the past year")
    out.append(f"<style>.d{{font-size:{FS}px;white-space:pre;}}</style>")
    out.append(card_label("the year, one character per day", P, 24, W - P, pal))

    # Month labels, placed on the column that carries each 1st.
    seen = set()
    for (row, col), (date, _) in sorted(cells.items(), key=lambda kv: kv[0][1]):
        if date.day <= 7 and date.month not in seen:
            seen.add(date.month)
            out.append(f'<text class="k" x="{LEFT + col * CW:.1f}" y="{52}">'
                       f"{date.strftime('%b').upper()}</text>")

    for row in range(7):
        y = 68 + row * LH
        base = y + FS * 0.78
        if row in (1, 3, 5):
            out.append(f'<text class="k" x="{P}" y="{y + FS * 0.72:.1f}">'
                       f"{['', 'MON', '', 'WED', '', 'FRI', ''][row]}</text>")

        # Group the row's days by ramp level and emit one <text> per level,
        # each carrying its own opacity. A <tspan> per day would triple the
        # file size for no visual gain, and the grid stays aligned because
        # every run is padded with spaces to the same column positions.
        levels: dict[int, list[str]] = {}
        for col in range(ncols):
            hit = cells.get((row, col))
            lv = level(hit[1]) if hit else -1        # -1 = outside the window
            levels.setdefault(lv, [])
        for lv in levels:
            if lv < 0:
                continue
            glyph = "\u00b7" if lv == 0 else RAMP[lv]
            line = "".join(
                glyph if (cells.get((row, c)) is not None
                          and level(cells[(row, c)][1]) == lv) else " "
                for c in range(ncols)
            )
            if not line.strip():
                continue
            fill = pal["faint"] if lv == 0 else pal["accent"]
            op = 1.0 if lv == 0 else 0.30 + 0.70 * (lv / steps)
            out.append(f'<text class="d" x="{LEFT}" y="{base:.1f}" '
                       f'xml:space="preserve" fill="{fill}" opacity="{op:.2f}"'
                       f'>{esc(line)}</text>')

    # Legend, using the same ramp so the mapping is readable rather than implied.
    ly = H - 26
    out.append(rule(P, ly - 16, W - P * 2, pal))
    out.append(f'<text class="k" x="{P}" y="{ly + 4}">LESS</text>')
    for i in range(steps + 1):
        x = P + 42 + i * 15
        fill = pal["faint"] if i == 0 else pal["accent"]
        op = 1.0 if i == 0 else 0.30 + 0.70 * (i / steps)
        ch = "·" if i == 0 else RAMP[i]
        out.append(f'<text class="d" x="{x}" y="{ly + 6}" fill="{fill}" '
                   f'opacity="{op:.2f}">{esc(ch)}</text>')
    out.append(f'<text class="k" x="{P + 42 + (steps + 1) * 15 + 6}" y="{ly + 4}">MORE</text>')

    peak_date, peak = max(days, key=lambda kv: kv[1])
    out.append(f'<text class="k" x="{W - P}" y="{ly + 4}" text-anchor="end">'
               f"BUSIEST DAY {peak} ON "
               f"{peak_date.strftime('%d %b %Y').lstrip('0').upper()}</text>")
    out.append("</svg>")
    return "".join(out)


# --------------------------------------------------------------------------
def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    login = os.environ.get("GH_LOGIN")
    if not token or not login:
        print("GITHUB_TOKEN and GH_LOGIN must be set", file=sys.stderr)
        return 2

    data = fetch(token, login)
    start, end = data["window"]
    print(f"  window {start} .. {end} (UTC days, pinned)")
    print(f"  {len(data['repos'])} public source repos")

    graphics = {
        "stats": draw_stats,
        "streak": draw_streak,
        "langs": draw_langs,
        "year": draw_year,
    }
    for name, fn in graphics.items():
        for theme, pal in THEMES.items():
            out = ROOT / f"{name}-{theme}.svg"
            out.write_text(fn(data, pal))
        size = (ROOT / f"{name}-dark.svg").stat().st_size
        print(f"  {name:<7} {size / 1024:>5.1f} KB x2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
