#!/usr/bin/env python3
"""Draw the contribution graphic from the GitHub GraphQL API.

Standard library only -- urllib for the API, nothing to break in CI.

    GITHUB_TOKEN=... GH_LOGIN=mustafa3252 python3 scripts/generate_stats.py

The determinism trap this handles: the contribution window is pinned to whole
UTC days. Left alone, contributionsCollection measures "the past year" from
the moment of the request, so two runs minutes apart bucket boundary days into
different weeks and the grid shifts. That is a commit every night, forever.
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
    return {"user": user, "window": (start, today)}


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


def draw_year(data: dict, pal: dict) -> str:
    """A square per day for the past year.

    The earlier version drew each day as a character from the portrait's ramp.
    At one glyph per day the shapes of the characters compete with the pattern
    they are meant to form, and the graphic reads as noise. Squares carry the
    same information with nothing left over to decode.
    """
    W, P = 880, 20
    days = calendar_days(data["user"])
    cal = data["user"]["contributionsCollection"]["contributionCalendar"]
    total = cal["totalContributions"]
    active = sum(1 for _, c in days if c)

    PITCH, CELL = 15, 12
    LEFT = P + 38
    GRID_Y = 62
    H = GRID_Y + 7 * PITCH + 52

    # Columns are weeks starting Sunday, matching GitHub's own graph.
    first = days[0][0]
    origin = first - dt.timedelta(days=(first.weekday() + 1) % 7)
    cells = {}
    for date, count in days:
        cells[((date.weekday() + 1) % 7, (date - origin).days // 7)] = (date, count)
    ncols = max(c for _, c in cells) + 1

    # Rank-based levels, not linear ones. A handful of very heavy days would
    # otherwise flatten every ordinary day onto the same step.
    counts = sorted(c for _, c in days if c)
    STEPS = 4
    OPACITY = {1: 0.22, 2: 0.42, 3: 0.66, 4: 0.92}

    def level(count: int) -> int:
        if not count or not counts:
            return 0
        rank = bisect.bisect_left(counts, count) / len(counts)
        return max(1, min(STEPS, 1 + int(rank * (STEPS - 1) + 0.5)))

    peak_date, peak = max(days, key=lambda kv: kv[1])

    # One subset, not two: nothing on this card is bold, and the font is
    # inlined per file so an unused face is dead weight in every byte served.
    o = head(W, H, pal, f"{total} contributions over the past year, one square "
                        f"per day; busiest day {peak}", subsets=("ui",))
    o.append(f'<defs><rect id="c" width="{CELL}" height="{CELL}" rx="2.5"/></defs>')
    o.append(card_label("the past year", P, 22, W - P, pal))
    o.append(f'<text class="k" x="{W - P}" y="22" text-anchor="end">'
             f"{total:,} CONTRIBUTIONS &#183; {active} ACTIVE DAYS</text>")

    seen = set()
    for (row, col), (date, _) in sorted(cells.items(), key=lambda kv: kv[0][1]):
        if date.day <= 7 and date.month not in seen:
            seen.add(date.month)
            o.append(f'<text class="k" x="{LEFT + col * PITCH:.0f}" y="{GRID_Y - 12}">'
                     f"{date.strftime('%b').upper()}</text>")

    # Bucket the cells by appearance and emit one <g> per bucket. Repeating
    # fill= and opacity= on 365 rects costs more than the grid itself.
    buckets: dict[tuple[str, float], list[str]] = {}
    for row in range(7):
        y = GRID_Y + row * PITCH
        if row in (1, 3, 5):
            o.append(f'<text class="k" x="{P}" y="{y + CELL - 2}">'
                     f"{['', 'MON', '', 'WED', '', 'FRI', ''][row]}</text>")
        for col in range(ncols):
            hit = cells.get((row, col))
            if hit is None:
                continue
            date, count = hit
            # The single brass cell is the busiest day of the year. Everywhere
            # else the accent is spent on status, never on magnitude.
            if date == peak_date:
                key = (pal["accent"], 1.0)
            elif count:
                key = (pal["ink"], OPACITY[level(count)])
            else:
                key = (pal["faint"], 1.0)
            buckets.setdefault(key, []).append(
                f'<use href="#c" x="{LEFT + col * PITCH}" y="{y}"/>'
            )

    for (fill, op), refs in sorted(buckets.items(), key=lambda kv: kv[0][1]):
        o.append(f'<g fill="{fill}" opacity="{op}">' + "".join(refs) + "</g>")

    fy = GRID_Y + 7 * PITCH + 16
    o.append(rule(P, fy, W - P * 2, pal))
    o.append(f'<text class="k" x="{P}" y="{fy + 21}">LESS</text>')
    for i in range(STEPS + 1):
        o.append(f'<use href="#c" x="{P + 40 + i * PITCH}" y="{fy + 11}" '
                 f'fill="{pal["faint"] if i == 0 else pal["ink"]}" '
                 f'opacity="{1.0 if i == 0 else OPACITY[i]}"/>')
    o.append(f'<text class="k" x="{P + 40 + (STEPS + 1) * PITCH + 4}" y="{fy + 21}">'
             f"MORE</text>")
    # Place the brass swatch off the measured width of its own label. The
    # .k class is 9.5px at 0.1em tracking, so each glyph advances 6.65px; a
    # guessed offset collides with the text as soon as the date gets longer.
    busiest = (f"BUSIEST DAY, {peak} ON "
               f"{peak_date.strftime('%d %b %Y').lstrip('0').upper()}")
    label_w = len(busiest) * (9.5 * 0.6 + 0.95)
    o.append(f'<use href="#c" x="{W - P - label_w - 20:.0f}" y="{fy + 11}" '
             f'fill="{pal["accent"]}"/>')
    o.append(f'<text class="k" x="{W - P}" y="{fy + 21}" text-anchor="end">'
             f"{busiest}</text>")
    o.append("</svg>")
    return "".join(o)


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

    graphics = {"year": draw_year}
    for name, fn in graphics.items():
        for theme, pal in THEMES.items():
            out = ROOT / f"{name}-{theme}.svg"
            out.write_text(fn(data, pal))
        size = (ROOT / f"{name}-dark.svg").stat().st_size
        print(f"  {name:<7} {size / 1024:>5.1f} KB x2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
