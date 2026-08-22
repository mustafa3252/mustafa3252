"""Shared, stdlib-only helpers for every SVG this repo draws.

Two things live here because every generator needs them and neither may pull
in a dependency: the palette (so the page reads as one design) and the
@font-face embedder (so the character grid is the same width on every OS).
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT_BUILD = ROOT / "assets" / "fonts" / "build"

# One accent, taken from GitHub's own contribution green so the year heatmap
# reads as what it is. Everything else is ink and dim. Deliberately no second
# hue: per-element colouring is what makes generated graphics look like noise.
THEMES = {
    "dark": {
        "ink":    "#d7dee7",
        "dim":    "#7d8590",
        "faint":  "#30363d",
        "accent": "#3fb950",
        "rule":   "#21262d",
    },
    "light": {
        "ink":    "#1f2328",
        "dim":    "#6e7781",
        "faint":  "#d8dee4",
        "accent": "#1a7f37",
        "rule":   "#d8dee4",
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
