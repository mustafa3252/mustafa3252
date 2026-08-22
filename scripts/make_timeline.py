#!/usr/bin/env python3
"""Experience as a vertical dotted timeline, most recent first.

Standard library only, so the scheduled workflow can regenerate it.

    python3 scripts/make_timeline.py
"""
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from svgkit import ROOT, STACK, THEMES, esc, font_face  # noqa: E402

# Quantised to the first of the current UTC month, which is the only way to get
# both properties at once. Read the clock directly and anything derived from it
# shifts every night, so the scheduled job commits every night forever. Freeze
# it to a literal and the graphic quietly goes stale instead. At month
# granularity the file is byte-identical for weeks, then changes once because
# something real changed.
NOW = dt.datetime.now(dt.timezone.utc).date().replace(day=1)

# ---------------------------------------------------------------------------
# The UCL start year is inferred: the résumé gives June 2026 as the completion
# date but no start date, and 2024 fits an MSc running alongside full-time
# work. Correct the year on that entry if it began later.
# ---------------------------------------------------------------------------

# Most recent first. (year, organisation, title, note, live)
ENTRIES = [
    ("2026", "First Concepts", "Founding Applied AI Engineer",
     "London · may 2026 → now", True),
    ("2025", "Chaser", "Software Engineer",
     "London · oct 2025 → apr 2026", False),
    ("2025", "IFRC", "AI Software Engineer, intern",
     "London · jun → sep 2025", False),
    ("2024", "University College London", "MSc Software Systems Engineering",
     "London · 2024 → jun 2026", False),
    ("2019", "Pandit Deendayal Energy University", "BTech Computer Engineering",
     "india · 2019 → 2023 · gpa 3.9 / 4.0", False),
]

W, P = 880, 20
YEAR_X = 74           # right edge of the year column
NODE_X = 104          # the dotted spine
TEXT_X = 132
ROW_H = 58
TOP = 40


def draw(pal: dict) -> str:
    H = TOP + len(ENTRIES) * ROW_H + 18

    o = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" aria-label="Timeline, most recent '
        f'first: founding applied AI engineer at First Concepts from May 2026; '
        f'software engineer at Chaser October 2025 to April 2026; AI software '
        f'engineering intern at IFRC June to September 2025; MSc Software '
        f'Systems Engineering at University College London, completed June '
        f'2026; BTech '
        f'Computer Engineering at Pandit Deendayal Energy University 2019 to '
        f'2023">',
        f"<defs><style>{font_face('JBMono', 'ui-medium', 500)}"
        f"text{{font-family:{STACK};fill:{pal['ink']};}}"
        f".y{{font-size:12px;fill:{pal['dim']};letter-spacing:.06em;}}"
        f".o{{font-size:14px;}}"
        f".r{{font-size:11.5px;fill:{pal['dim']};}}"
        f".m{{font-size:9.5px;fill:{pal['dim']};letter-spacing:.1em;}}"
        "</style></defs>",
    ]

    first_y = TOP + 14
    last_y = TOP + (len(ENTRIES) - 1) * ROW_H + 14

    # The spine. Dots rather than a rule: the gaps carry the sense of elapsed
    # time between entries without pretending to measure it.
    o.append(f'<line x1="{NODE_X}" y1="{first_y}" x2="{NODE_X}" y2="{last_y}" '
             f'stroke="{pal["dim"]}" stroke-width="1.6" stroke-linecap="round" '
             f'stroke-dasharray="0.1 7" opacity="0.55"/>')

    for i, (year, org, title, note, live) in enumerate(ENTRIES):
        y = TOP + i * ROW_H
        cy = y + 14

        o.append(f'<text class="y" x="{YEAR_X}" y="{cy + 4}" '
                 f'text-anchor="end">{esc(year)}</text>')

        if live:
            # The only filled node, and the only brass on the graphic: it marks
            # the one entry that has not ended.
            o.append(f'<circle cx="{NODE_X}" cy="{cy}" r="9" '
                     f'fill="{pal["accent"]}" opacity="0.16"/>')
            o.append(f'<circle cx="{NODE_X}" cy="{cy}" r="4.5" '
                     f'fill="{pal["accent"]}"/>')
        else:
            o.append(f'<circle cx="{NODE_X}" cy="{cy}" r="4" fill="none" '
                     f'stroke="{pal["dim"]}" stroke-width="1.5"/>')

        o.append(f'<text class="o" x="{TEXT_X}" y="{cy + 5}">{esc(org)}</text>')
        o.append(f'<text class="r" x="{TEXT_X}" y="{cy + 23}">{esc(title)}</text>')
        o.append(f'<text class="m" x="{W - P}" y="{cy + 4}" text-anchor="end"'
                 f'{" fill=" + chr(34) + pal["accent"] + chr(34) if live else ""}'
                 f">{esc(note.upper())}</text>")

    o.append("</svg>")
    return "".join(o)


def main() -> int:
    for theme, pal in THEMES.items():
        out = ROOT / f"timeline-{theme}.svg"
        out.write_text(draw(pal))
        print(f"  wrote {out.name}  {out.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
