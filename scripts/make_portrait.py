#!/usr/bin/env python3
"""Photo -> self-typing ASCII portrait, as a pair of self-contained SVGs.

Run locally (needs rembg/opencv); the result is committed. CI never runs this.

    python3 scripts/make_portrait.py assets/portrait-src.jpg

Why each stage is here, in order:

  rembg cut-out     everything outside the subject is forced to white, which
                    maps to the blank end of the ramp. Skip it and the
                    background fills with '@' and drowns the portrait.
  face crop         ASCII has ~13 brightness levels; a face that occupies 30%
                    of the frame gets ~30 characters across and the eyes will
                    not resolve. Crop chin-to-above-hair.
  bilateral filter  smooths skin while keeping the edges that carry the face.
  CLAHE clip 3.0    local contrast per tile. Global autocontrast leaves a
                    flatly-lit face as a single tone.
  gamma (v/255)^G   the fix. Without it the face comes out washed out and
                    featureless; this is what makes brows, lids and lips
                    survive the downsample to 13 levels.
  ramp map          leading space clears the background to nothing.
"""
import argparse
import pathlib
import sys

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from svgkit import ROOT, STACK, THEMES, font_face  # noqa: E402

RAMP = " .`:-=+*cs#%@"        # light -> dark, 13 steps
CHAR_W = 7.74                  # 0.600 em at font-size 12.9
FONT_SIZE = 12.9
LINE_H = CHAR_W / 0.48         # keeps the cell aspect the row count assumes
PAD = 10.0

STAGGER = 0.085                # seconds between one row starting and the next
ROW_DUR = 0.45                 # seconds for a single row to finish wiping in


def cutout(path: pathlib.Path) -> np.ndarray:
    """Remove the background and composite the subject onto white."""
    from rembg import remove

    src = Image.open(path).convert("RGBA")
    cut = remove(src)
    white = Image.new("RGBA", cut.size, (255, 255, 255, 255))
    return np.array(Image.alpha_composite(white, cut).convert("RGB")), np.array(cut)[:, :, 3]


YUNET_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)


def _detect_face(rgb: np.ndarray):
    """Return (x, y, w, h) of the largest face, or None.

    OpenCV 4 ships Haar cascades in the Python bindings; OpenCV 5 dropped them
    and offers the DNN detector YuNet instead. Try whichever this build has.
    """
    h, w = rgb.shape[:2]
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    if hasattr(cv2, "CascadeClassifier"):                       # OpenCV 4
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        faces = cascade.detectMultiScale(gray, 1.05, 5, minSize=(w // 12, h // 12))
        if len(faces):
            return max(faces, key=lambda f: f[2] * f[3])

    if hasattr(cv2, "FaceDetectorYN"):                          # OpenCV 5
        import urllib.request

        cache = pathlib.Path.home() / ".cache" / "ascii-readme"
        cache.mkdir(parents=True, exist_ok=True)
        model = cache / "face_detection_yunet.onnx"
        if not model.exists():
            print("  fetching YuNet face model (~350 KB, once)")
            ctx = None
            try:                       # macOS python installs often lack roots
                import certifi, ssl
                ctx = ssl.create_default_context(cafile=certifi.where())
            except ImportError:
                pass
            with urllib.request.urlopen(YUNET_URL, context=ctx) as r:
                model.write_bytes(r.read())
        det = cv2.FaceDetectorYN.create(str(model), "", (w, h), 0.6, 0.3, 5000)
        _, faces = det.detect(bgr)
        if faces is not None and len(faces):
            best = max(faces, key=lambda f: f[2] * f[3])
            return tuple(int(round(v)) for v in best[:4])

    return None


def crop_to_face(rgb: np.ndarray, alpha: np.ndarray, mode: str, pad: float = 0.62) -> np.ndarray:
    """Tighten the frame so the face actually gets enough characters."""
    h, w = rgb.shape[:2]
    if mode == "none":
        return rgb

    box = None
    if mode == "face":
        face = _detect_face(rgb)
        if face is not None:
            fx, fy, fw, fh = face
            # Detectors box the features (brow to lip), not the head. Expand
            # asymmetrically -- up for hair, further down for the chin -- to
            # land on the guide's framing: chin to just above the hairline.
            cx = fx + fw / 2
            box = (
                cx - fw * pad,
                fy - fh * 0.45,
                cx + fw * pad,
                fy + fh * 1.15,
            )
        else:
            print("  no face found, falling back to subject bounds", file=sys.stderr)

    if box is None:                                   # subject bounds from alpha
        ys, xs = np.where(alpha > 16)
        if not len(xs):
            return rgb
        box = (xs.min(), ys.min(), xs.max(), ys.max())

    x0, y0, x1, y1 = (int(round(v)) for v in box)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    return rgb[y0:y1, x0:x1]


def to_ascii(rgb: np.ndarray, cols: int, gamma: float, clip: float,
             sharp: float) -> list[str]:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    # Upsample first. Thin features -- glasses frames, lash lines, the shadow
    # under a lip -- are already near sub-pixel in a small crop, and every
    # later stage would average them away for good.
    if min(gray.shape) < 700:
        scale = 700 / min(gray.shape)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # Denoise before boosting contrast, not after: CLAHE amplifies whatever
    # JPEG blocking survives, and the ramp turns that into visible static.
    gray = cv2.bilateralFilter(gray, 11, 75, 75)

    # Unsharp mask over a wide radius. ASCII draws with shadow, and a flatly
    # lit face has almost none -- this puts a usable edge back under the brow,
    # the nose and the lip line so they survive the 13-level quantisation.
    if sharp:
        blur = cv2.GaussianBlur(gray, (0, 0), 9)
        gray = cv2.addWeighted(gray, 1 + sharp, blur, -sharp, 0)

    # Stretch the *subject* across the full range. The cut-out background is
    # pure white, so it would pin the maximum at 255 and make a global
    # normalisation a no-op -- which is how a face ends up occupying only the
    # top four steps of a 13-step ramp and reading as one dark blob.
    subject = gray[gray < 250]
    if subject.size:
        lo, hi = np.percentile(subject, (1, 99))
        if hi - lo > 8:
            gray = np.clip(
                (gray.astype(np.float32) - lo) * (255.0 / (hi - lo)), 0, 255
            ).astype(np.uint8)

    # Local contrast per tile. Global autocontrast leaves a flatly-lit face as
    # a single tone no matter how far you stretch it.
    gray = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8)).apply(gray)

    # The darkening curve. Without it the face comes out washed out and
    # featureless; this is what makes brows, lids and lips survive the drop
    # to 13 levels.
    v = (gray.astype(np.float32) / 255.0) ** gamma
    gray = np.clip(v * 255.0, 0, 255).astype(np.uint8)

    h, w = gray.shape
    rows = max(1, int(round(cols * (h / w) * 0.48)))
    small = cv2.resize(gray, (cols, rows), interpolation=cv2.INTER_AREA)

    n = len(RAMP) - 1
    out = []
    for row in small:
        idx = ((255 - row.astype(np.int32)) * n) // 255
        out.append("".join(RAMP[i] for i in idx))
    return [r.rstrip() for r in out]


def to_svg(art: list[str], theme: str, cols: int, display_w: int) -> str:
    """One clipPath per row, each animating width 0 -> full, with a block
    riding the wipe edge as a cursor. fill='freeze' everywhere, so the
    portrait prints once and stops. No looping."""
    pal = THEMES[theme]
    rows = len(art)
    vb_w = cols * CHAR_W + PAD * 2
    vb_h = rows * LINE_H + PAD * 2
    display_h = round(display_w * vb_h / vb_w)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vb_w:.2f} {vb_h:.2f}" '
        f'width="{display_w}" height="{display_h}" role="img" '
        f'aria-label="ASCII portrait that types itself in">',
        "<defs><style>",
        font_face("JBMono", "ramp"),
        f"text{{font-family:{STACK};font-size:{FONT_SIZE}px;"
        f"fill:{pal['ink']};white-space:pre;}}",
        "</style>",
    ]

    for i, line in enumerate(art):
        width = len(line) * CHAR_W
        begin = f"{i * STAGGER:.3f}s"
        parts.append(
            f'<clipPath id="c{i}"><rect x="{PAD:.2f}" y="0" width="0" height="{vb_h:.2f}">'
            f'<animate attributeName="width" from="0" to="{width:.2f}" '
            f'dur="{ROW_DUR}s" begin="{begin}" fill="freeze"/></rect></clipPath>'
        )
    parts.append("</defs>")

    for i, line in enumerate(art):
        if not line:
            continue
        y = PAD + (i + 0.8) * LINE_H
        width = len(line) * CHAR_W
        begin = f"{i * STAGGER:.3f}s"
        safe = line.replace("&", "&amp;").replace("<", "&lt;")
        parts.append(
            f'<text x="{PAD:.2f}" y="{y:.2f}" xml:space="preserve" '
            f'clip-path="url(#c{i})">{safe}</text>'
        )
        # The cursor: rides the wipe edge, then switches off for good.
        parts.append(
            f'<rect x="{PAD:.2f}" y="{y - LINE_H * 0.72:.2f}" width="{CHAR_W:.2f}" '
            f'height="{LINE_H * 0.82:.2f}" fill="{pal["accent"]}" opacity="0">'
            f'<set attributeName="opacity" to="0.85" begin="{begin}"/>'
            f'<animate attributeName="x" from="{PAD:.2f}" to="{PAD + width:.2f}" '
            f'dur="{ROW_DUR}s" begin="{begin}" fill="freeze"/>'
            f'<set attributeName="opacity" to="0" begin="{i * STAGGER + ROW_DUR:.3f}s"/>'
            f"</rect>"
        )

    parts.append("</svg>")
    return "".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("photo", type=pathlib.Path)
    ap.add_argument("--cols", type=int, default=90)
    ap.add_argument("--width", type=int, default=460, help="displayed px width")
    ap.add_argument("--gamma", type=float, default=0.8, help="tone curve exponent")
    ap.add_argument("--clip", type=float, default=3.0, help="CLAHE clip limit")
    ap.add_argument("--sharp", type=float, default=0.6, help="unsharp mask amount")
    ap.add_argument("--crop", choices=["face", "subject", "none"], default="face")
    ap.add_argument("--pad", type=float, default=0.62,
                    help="crop half-width as a multiple of the detected face width")
    ap.add_argument("--txt", action="store_true", help="also dump the raw grid")
    args = ap.parse_args()

    print(f"  reading {args.photo}")
    rgb, alpha = cutout(args.photo)
    rgb = crop_to_face(rgb, alpha, args.crop, args.pad)
    print(f"  crop -> {rgb.shape[1]}x{rgb.shape[0]}")

    art = to_ascii(rgb, args.cols, args.gamma, args.clip, args.sharp)
    print(f"  grid -> {args.cols} cols x {len(art)} rows"
          f"  (~{len(art) * STAGGER + ROW_DUR:.1f}s to type)")

    if args.txt:
        (ROOT / "portrait.txt").write_text("\n".join(art) + "\n")

    for theme in ("dark", "light"):
        out = ROOT / f"portrait-{theme}.svg"
        out.write_text(to_svg(art, theme, args.cols, args.width))
        print(f"  wrote {out.name}  {out.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
