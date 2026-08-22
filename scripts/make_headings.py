#!/usr/bin/env python3
"""Section headings and the name plate, as SVG.

An image is the only way to put your own typeface on a README heading:
GitHub strips <style>, style="", class="", inline <svg> and <font>, so the
text itself can only ever be GitHub's sans or its monospace.

Stated plainly, because it is a real cost: image headings have no anchor
links, so GitHub's README outline goes empty. The alt text carries the word
for screen readers and for anyone browsing with images off.

    python3 scripts/make_headings.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from svgkit import ROOT, STACK, THEMES, esc, font_face  # noqa: E402

W = 880
SECTIONS = ["experience", "projects", "stack", "contributions", "elsewhere"]

NAME = "Mustafa Africawala"
TAGLINE = "founding applied ai engineer at First Concepts · msc from UCL · London"


def heading(text: str, pal: dict) -> str:
    """Lowercase mono label with a hairline rule running to the right edge."""
    H, FS, P = 30, 13.0, 0
    # 0.600 em advance, plus the tracking applied below.
    adv = FS * 0.6 + 1.9
    tw = len(text) * adv
    rx = P + tw + 14
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" aria-label="{esc(text)}">'
        f"<defs><style>{font_face('JBMono', 'headings', 500)}"
        f"text{{font-family:{STACK};font-size:{FS}px;font-weight:500;"
        f"fill:{pal['ink']};letter-spacing:.15em;}}</style></defs>"
        f'<text x="{P}" y="{H / 2 + FS * 0.36:.1f}">{esc(text)}</text>'
        f'<rect x="{rx:.1f}" y="{H / 2 - 0.5:.1f}" width="{W - rx:.1f}" '
        f'height="1" fill="{pal["rule"]}"/>'
        f'<rect x="{W - 3}" y="{H / 2 - 3:.1f}" width="3" height="6" '
        f'fill="{pal["accent"]}"/>'
        f"</svg>"
    )


def nameplate(pal: dict) -> str:
    H = 108
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" '
        f'aria-label="{esc(NAME)} — {esc(TAGLINE)}">'
        f"<defs><style>"
        f"{font_face('JBMono', 'plate-sub', 400)}"
        f"{font_face('JBMonoB', 'plate', 700)}"
        f"text{{font-family:{STACK};fill:{pal['ink']};}}"
        f".n{{font-family:'JBMonoB',{STACK};font-size:31px;font-weight:700;"
        f"letter-spacing:-.02em;}}"
        f".t{{font-size:13px;fill:{pal['dim']};letter-spacing:.04em;}}"
        f".h{{font-size:11px;fill:{pal['dim']};letter-spacing:.2em;}}"
        f"</style></defs>"
        f'<text class="h" x="0" y="18">@mustafa3252</text>'
        f'<text class="n" x="0" y="56">{esc(NAME)}</text>'
        f'<text class="t" x="0" y="80">{esc(TAGLINE)}</text>'
        # Well clear of the tagline baseline -- any closer and it reads as an
        # accidental underline on the first word rather than as a rule.
        f'<rect x="0" y="{H - 10}" width="52" height="2" fill="{pal["accent"]}"/>'
        f"</svg>"
    )


def main() -> int:
    total = 0
    for theme, pal in THEMES.items():
        for name, svg in [("name", nameplate(pal))] + [
            (s, heading(s, pal)) for s in SECTIONS
        ]:
            out = ROOT / f"hd-{name}-{theme}.svg"
            out.write_text(svg)
            total += out.stat().st_size
    print(f"  {(len(SECTIONS) + 1) * 2} heading files, {total / 1024:.1f} KB total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
