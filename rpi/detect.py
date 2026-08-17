#!/usr/bin/env python3
"""Lightweight change detection to flag frames that likely contain an insect.

On an otherwise-static scene, a frame that differs from the one before it means
*something appeared or moved* — most likely a visiting insect. This compares two
frames (downscaled, blurred, grayscale absolute difference) and reports whether
the change is small-and-localized (insect-like) versus none (empty) or huge
(a light/camera shift, which we ignore).

It is a heuristic proxy, not an ML classifier — cheap enough to run on a Pi every
cycle. A trained insect classifier is a future upgrade (see docs/IMPROVEMENTS.md).

Tunables via env: DETECT_W, DETECT_DIFF, DETECT_MIN_FRAC, DETECT_MAX_FRAC.
"""
import os

try:
    from PIL import Image, ImageChops, ImageFilter
    _ok = True
except ImportError:
    _ok = False

SCALE_W = int(os.environ.get("DETECT_W", "320"))          # downscale width
DIFF_THRESH = int(os.environ.get("DETECT_DIFF", "28"))    # per-pixel diff counted as "changed"
MIN_FRAC = float(os.environ.get("DETECT_MIN_FRAC", "0.0008"))  # below = sensor noise
MAX_FRAC = float(os.environ.get("DETECT_MAX_FRAC", "0.15"))    # above = light/camera shift


def available():
    return _ok


def _prep(path):
    im = Image.open(path).convert("L")
    h = max(1, int(im.height * SCALE_W / im.width))
    return im.resize((SCALE_W, h)).filter(ImageFilter.GaussianBlur(1))


def score_frame(prev_path, cur_path):
    """Compare cur to prev. Returns (insect: bool, score: float 0..1).

    score is the changed-pixel fraction normalized into the plausible band;
    insect is True when the change is within [MIN_FRAC, MAX_FRAC] (localized).
    """
    if not _ok:
        return False, 0.0
    try:
        a, b = _prep(prev_path), _prep(cur_path)
    except Exception:
        return False, 0.0
    mask = ImageChops.difference(a, b).point(lambda p: 255 if p >= DIFF_THRESH else 0)
    total = a.width * a.height
    changed = mask.histogram()[255]
    frac = changed / total if total else 0.0
    insect = MIN_FRAC <= frac <= MAX_FRAC
    score = round(min(1.0, frac / MAX_FRAC), 3)
    return insect, score


if __name__ == "__main__":                                # quick CLI test: detect.py a.jpg b.jpg
    import sys
    if len(sys.argv) == 3:
        print(score_frame(sys.argv[1], sys.argv[2]))
    else:
        print("usage: detect.py <prev.jpg> <cur.jpg>   (PIL available: %s)" % _ok)
