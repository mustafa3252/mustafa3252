#!/usr/bin/env python3
"""Render portrait.txt to a PNG so the grid can be judged by eye, not read."""
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
SIZE = 13
CW, LH = SIZE * 0.6, SIZE * 1.25

lines = (ROOT / "portrait.txt").read_text().split("\n")
font = ImageFont.truetype(str(ROOT / "assets/fonts/JetBrainsMono-Regular.ttf"), SIZE)
W = int(max(len(l) for l in lines) * CW) + 20
H = int(len(lines) * LH) + 20
bg, fg = (13, 17, 23), (215, 222, 231)
img = Image.new("RGB", (W, H), bg)
d = ImageDraw.Draw(img)
for i, line in enumerate(lines):
    d.text((10, 10 + i * LH), line, font=font, fill=fg)
out = ROOT / "portrait-preview.png"
img.save(out)
print(f"{out}  {W}x{H}")
