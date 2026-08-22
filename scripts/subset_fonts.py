#!/usr/bin/env python3
"""Subset JetBrains Mono to per-role woff2 blobs, emitted as base64 text.

Run locally after changing which glyphs the graphics use:

    python3 scripts/subset_fonts.py

The generators are stdlib-only and simply read the .b64 files, so CI never
needs fonttools installed. Font is SIL OFL 1.1; assets/fonts/OFL.txt ships
next to it, as the licence requires.
"""
import base64
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "fonts"
OUT = SRC / "build"

# The 13-step brightness ramp the portrait draws with, plus nothing else.
RAMP = " .`:-=+*cs#%@"

# Everything the data graphics and headings can print.
LATIN = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " .,:;'\"/\\|-_+=<>()[]{}%#@&*!?~^$"
    # Backtick is a ramp step; the middot and arrow are used as separators in
    # the cards. A glyph missing from the subset falls back to a font with a
    # different advance width, which would quietly break the 0.600 grid.
    "`\u00b7\u2192\u2014"
)

# Role-specific sets. A heading only ever prints its own word, so shipping it
# 94 glyphs is most of a kilobyte wasted in every one of the eight files.
# Keep these in sync with SECTIONS / NAME / TAGLINE in make_headings.py.
SECTION_WORDS = "experience projects stack signals elsewhere"
PLATE_NAME = "Mustafa Africawala"
PLATE_SUB = ("@mustafa3252 founding applied ai engineer at First Concepts "
             "\u00b7 msc at UCL \u00b7 London")

uniq = lambda *parts: "".join(sorted(set("".join(parts))))

JOBS = [
    ("ramp",       "JetBrainsMono-Regular.ttf", RAMP),
    ("ui",         "JetBrainsMono-Regular.ttf", LATIN),
    ("ui-medium",  "JetBrainsMono-Medium.ttf",  LATIN),
    ("ui-bold",    "JetBrainsMono-Bold.ttf",    LATIN),
    ("headings",   "JetBrainsMono-Medium.ttf",  uniq(SECTION_WORDS)),
    ("plate",      "JetBrainsMono-Bold.ttf",    uniq(PLATE_NAME)),
    ("plate-sub",  "JetBrainsMono-Regular.ttf", uniq(PLATE_SUB)),
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for name, src, text in JOBS:
        src_path = SRC / src
        if not src_path.exists():
            print(f"missing source font: {src_path}", file=sys.stderr)
            return 1
        woff2 = OUT / f"{name}.woff2"
        subprocess.run(
            [
                "pyftsubset", str(src_path),
                f"--text={text}",
                "--flavor=woff2",
                "--layout-features=",
                "--no-hinting",
                "--desubroutinize",
                f"--output-file={woff2}",
            ],
            check=True,
        )
        blob = woff2.read_bytes()
        (OUT / f"{name}.woff2.b64").write_text(base64.b64encode(blob).decode())
        woff2.unlink()
        total += len(blob)
        print(f"  {name:<10} {len(text):>3} glyphs  {len(blob)/1024:>6.1f} KB")
    print(f"  {'total':<10} {'':>3}         {total/1024:>6.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
