#!/usr/bin/env python3
"""Render README.md the way GitHub will, for local checking.

    python3 scripts/preview.py && open readme-preview.html

Two things this gets right that are easy to get wrong:

  * It asks GitHub's own rendering API, which applies the same sanitiser as
    the site, so anything stripped here is stripped in production.
  * It uses mode=markdown, not mode=gfm. The gfm mode is for issue comments
    and turns every newline into a <br>, which doubles up the explicit <br>
    tags a README uses for line-length control and sends you hunting a bug
    that does not exist.

Note that the portrait will look blank in a screenshot: capturing restarts
SMIL, so an animated SVG re-renders from frame zero. Watch it in a real
browser window instead.
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSS = """
body{margin:0;background:#0d1117;color:#e6edf3;
 font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:1012px;margin:0 auto;padding:32px}
.md{max-width:890px;border:1px solid #30363d;border-radius:6px;padding:32px}
.md.light{background:#fff;color:#1f2328;border-color:#d1d9e0}
a{color:#4493f8;text-decoration:none}.light a{color:#0969da}
samp{font-family:ui-monospace,SFMono-Regular,monospace;font-size:12px;color:#8b949e}
.light samp{color:#59636e}
blockquote{border-left:.25em solid #3d444d;padding:0 1em;color:#9198a1;margin:16px 0}
.light blockquote{border-color:#d1d9e0;color:#59636e}
img{max-width:100%}p{margin:0 0 16px}details{margin-top:24px}summary{cursor:pointer}
h4{font:600 11px ui-monospace;letter-spacing:.2em;color:#7d8590;margin:0 0 12px}
"""


def main() -> int:
    md = (ROOT / "README.md").read_text()
    proc = subprocess.run(
        ["gh", "api", "-X", "POST", "/markdown",
         "-f", "mode=markdown", "-f", f"text={md}"],
        capture_output=True, text=True,
    )
    if proc.returncode:
        print(proc.stderr, file=sys.stderr)
        return 1
    light = proc.stdout

    # Stand in for GitHub's <themed-picture> component, which swaps <picture>
    # sources to the *GitHub* theme rather than the OS one.
    dark = re.sub(r'src="([a-z0-9-]+)-light\.svg"', r'src="\1-dark.svg"', light)

    out = ROOT / "readme-preview.html"
    out.write_text(
        f"<!doctype html><meta charset=utf-8><style>{CSS}</style><div class=wrap>"
        f"<h4>DARK</h4><div class='md'>{dark}</div>"
        f"<h4 style='margin-top:40px'>LIGHT</h4><div class='md light'>{light}</div>"
        f"</div>"
    )
    print(f"  wrote {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
