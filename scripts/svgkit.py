"""Shared, stdlib-only helpers for every SVG this repo draws.

Two things live here because every generator needs them and neither may pull
in a dependency: the palette (so the page reads as one design) and the
@font-face embedder (so the character grid is the same width on every OS).
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT_BUILD = ROOT / "assets" / "fonts" / "build"

# Warm monochrome against GitHub's cool near-black, plus exactly one accent:
# brass, the colour of instrumentation. It is spent in four places on the whole
# page -- the typing cursor, the live span, the peak marker, the heading tick --
# and nowhere else. Bars and the heatmap are ink at varying opacity, because a
# second hue would buy nothing and cost the page its discipline.
THEMES = {
    "dark": {
        "ink":    "#e8e5e0",
        "dim":    "#8c867c",
        "faint":  "#2c2925",
        "accent": "#d4a640",
        "rule":   "#282520",
    },
    "light": {
        "ink":    "#1c1a17",
        "dim":    "#6d675e",
        "faint":  "#e4e0d9",
        "accent": "#a8761b",
        "rule":   "#ded9d2",
    },
}

# Fallbacks are all 0.600-advance faces, so a viewer who somehow blocks the
# embedded font still gets the right grid. Consolas (0.55) is never reached.
STACK = "'JBMono','Liberation Mono','DejaVu Sans Mono','Noto Sans Mono',monospace"


def font_face(family: str, subset: str, weight: int = 400) -> str:
    """Inline one subset as a base64 woff2 @font-face rule.

    An external font URL cannot work here: these SVGs load through <img>, and
    browsers refuse subresource fetches for image documents. A data: URI is
    same-document, so it loads.
    """
    b64 = (FONT_BUILD / f"{subset}.woff2.b64").read_text().strip()
    return (
        f"@font-face{{font-family:'{family}';"
        f"src:url(data:font/woff2;base64,{b64}) format('woff2');"
        f"font-weight:{weight};font-style:normal;font-display:block;}}"
    )


def esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
