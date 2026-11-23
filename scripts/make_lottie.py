"""Generate the Stryk loader animation as a Lottie file.

    python scripts/make_lottie.py

A cricket ball in the brand orange: spinning on its seam, falling with speed
streaks, squashing as it lands, and kicking out an impact ring. Written out
rather than downloaded.

Why not a stock file: every cricket animation on LottieFiles sits behind an
account for the raw JSON, and they all carry the Lottie Simple License, whose
terms have to travel with the file wherever it is distributed - including to
every browser that loads this page. Generating it keeps the product's licensing
simple and makes the ball the same one that is in the logo.

To use a stock animation instead, download its JSON and save it over
frontend/public/brand/ball-loader.json. The loader component fetches that path,
so nothing else needs to change.

Output: frontend/public/brand/ball-loader.json
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "brand" / "ball-loader.json"

W = H = 200
FPS = 60
DUR = 72  # 1.2s loop

ORANGE = [252 / 255, 82 / 255, 0 / 255, 1]
WHITE = [1, 1, 1, 1]
BLACK = [0, 0, 0, 1]

R = 27.0                 # ball radius
APEX = 42.0              # ball base at the top of the bounce
GROUND = 126.0           # ball base at the moment of contact
LAND = DUR // 2          # frame the ball touches down


def hold(x_out=0.6, y_out=0.0, x_in=0.4, y_in=1.0):
    return {"o": {"x": [x_out], "y": [y_out]}, "i": {"x": [x_in], "y": [y_in]}}


def kf(t, value, **ease):
    frame = {"t": t, "s": value if isinstance(value, list) else [value]}
    frame.update(ease or hold())
    return frame


def tr(anchor=(0, 0)):
    """The transform every shape group needs to close with."""
    return {
        "ty": "tr",
        "p": {"a": 0, "k": [0, 0]},
        "a": {"a": 0, "k": list(anchor)},
        "s": {"a": 0, "k": [100, 100]},
        "r": {"a": 0, "k": 0},
        "o": {"a": 0, "k": 100},
        "sk": {"a": 0, "k": 0},
        "sa": {"a": 0, "k": 0},
    }


def ellipse(size, name="ellipse"):
    return {"ty": "el", "nm": name, "p": {"a": 0, "k": [0, 0]},
            "s": {"a": 0, "k": list(size)}, "d": 1}


def fill(colour, opacity=100):
    return {"ty": "fl", "nm": "fill", "c": {"a": 0, "k": colour},
            "o": {"a": 0, "k": opacity}, "r": 1}


def stroke(colour, width, opacity=100):
    return {"ty": "st", "nm": "stroke", "c": {"a": 0, "k": colour},
            "o": {"a": 0, "k": opacity}, "w": {"a": 0, "k": width},
            "lc": 2, "lj": 1, "ml": 4}


def layer(index, name, ks, shapes, **extra):
    base = {
        "ddd": 0, "ind": index, "ty": 4, "nm": name, "sr": 1,
        "ks": ks, "ao": 0, "shapes": shapes,
        "ip": 0, "op": DUR, "st": 0, "bm": 0,
    }
    base.update(extra)
    return base


# --------------------------------------------------------------- the ball
def ball_layer() -> dict:
    """Fall, squash, rise.

    The anchor sits at the bottom of the ball so that squashing presses it into
    the ground instead of shrinking it towards its own middle, which is what
    makes a bounce read as weight rather than as a scaling circle.
    """
    squash_in, squash_out = LAND - 3, LAND + 3
    return layer(
        1,
        "ball",
        {
            "o": {"a": 0, "k": 100},
            # Spin accelerates into the bounce and carries on through it.
            "r": {"a": 1, "k": [
                kf(0, 0, **hold(0.4, 0.0, 0.6, 1.0)),
                kf(DUR, 400),
            ]},
            "p": {"a": 1, "k": [
                kf(0, [100, APEX + R, 0], **hold(0.75, 0.0, 0.95, 0.85)),
                kf(LAND, [100, GROUND + R, 0], **hold(0.05, 0.15, 0.25, 1.0)),
                kf(DUR, [100, APEX + R, 0]),
            ]},
            "a": {"a": 0, "k": [0, R, 0]},
            "s": {"a": 1, "k": [
                # Stretched while falling, flattened on contact, settled after.
                kf(0, [97, 103, 100], **hold(0.6, 0.0, 0.5, 1.0)),
                kf(squash_in, [100, 100, 100], **hold(0.2, 0.0, 0.4, 1.0)),
                kf(LAND, [122, 80, 100], **hold(0.2, 0.0, 0.3, 1.0)),
                kf(squash_out, [96, 106, 100], **hold(0.4, 0.0, 0.5, 1.0)),
                kf(DUR, [97, 103, 100]),
            ]},
        },
        [
            # Lottie paints shapes[0] on top, so the seam comes before the body.
            {"ty": "gr", "nm": "seam inner",
             "it": [ellipse([20, 2 * R - 6]), stroke(WHITE, 3.2), tr()]},
            {"ty": "gr", "nm": "seam outer",
             "it": [ellipse([38, 2 * R - 2]), stroke(WHITE, 2.0, 80), tr()]},
            {"ty": "gr", "nm": "body",
             "it": [ellipse([2 * R, 2 * R]), fill(ORANGE), tr()]},
        ],
    )


# ------------------------------------------------------------- the trimmings
def streaks_layer() -> dict:
    """Speed lines above the ball, visible only through the fast part of the fall."""
    return layer(
        2,
        "speed streaks",
        {
            "o": {"a": 1, "k": [
                kf(0, 0, **hold()),
                kf(int(LAND * 0.45), 55, **hold()),
                kf(LAND - 4, 0, **hold()),
                kf(DUR, 0),
            ]},
            "r": {"a": 0, "k": 0},
            "p": {"a": 1, "k": [
                kf(0, [100, APEX - 6, 0], **hold(0.75, 0.0, 0.95, 0.85)),
                kf(LAND, [100, GROUND - 4, 0], **hold()),
                kf(DUR, [100, APEX - 6, 0]),
            ]},
            "a": {"a": 0, "k": [0, 0, 0]},
            "s": {"a": 0, "k": [100, 100, 100]},
        },
        [
            {"ty": "gr", "nm": "streak group", "it": [
                {"ty": "sh", "nm": "left", "ks": {"a": 0, "k": {
                    "c": False, "v": [[-13, -26], [-13, -6]], "i": [[0, 0], [0, 0]],
                    "o": [[0, 0], [0, 0]]}}},
                {"ty": "sh", "nm": "mid", "ks": {"a": 0, "k": {
                    "c": False, "v": [[0, -34], [0, -10]], "i": [[0, 0], [0, 0]],
                    "o": [[0, 0], [0, 0]]}}},
                {"ty": "sh", "nm": "right", "ks": {"a": 0, "k": {
                    "c": False, "v": [[13, -26], [13, -6]], "i": [[0, 0], [0, 0]],
                    "o": [[0, 0], [0, 0]]}}},
                stroke(ORANGE, 3.0),
                tr(),
            ]},
        ],
    )


def impact_layer() -> dict:
    """A ring that expands out of the bounce and fades, so the landing lands."""
    return layer(
        3,
        "impact ring",
        {
            "o": {"a": 1, "k": [
                kf(LAND - 1, 0, **hold()),
                kf(LAND + 1, 70, **hold()),
                kf(LAND + 14, 0, **hold()),
                kf(DUR, 0),
            ]},
            "r": {"a": 0, "k": 0},
            "p": {"a": 0, "k": [100, GROUND + R, 0]},
            "a": {"a": 0, "k": [0, 0, 0]},
            "s": {"a": 1, "k": [
                kf(LAND, [30, 30, 100], **hold(0.1, 0.0, 0.3, 1.0)),
                kf(LAND + 14, [135, 135, 100]),
                kf(DUR, [135, 135, 100]),
            ]},
        },
        [
            {"ty": "gr", "nm": "ring group",
             "it": [ellipse([52, 14]), stroke(ORANGE, 3.0), tr()]},
        ],
    )


def shadow_layer() -> dict:
    """Tracks the ball: tight and dark underneath it, wide and faint when it is up."""
    return layer(
        4,
        "shadow",
        {
            "o": {"a": 1, "k": [
                kf(0, 12, **hold()),
                kf(LAND, 36, **hold()),
                kf(DUR, 12),
            ]},
            "r": {"a": 0, "k": 0},
            "p": {"a": 0, "k": [100, GROUND + R + 2, 0]},
            "a": {"a": 0, "k": [0, 0, 0]},
            "s": {"a": 1, "k": [
                kf(0, [58, 58, 100], **hold()),
                kf(LAND, [120, 120, 100], **hold()),
                kf(DUR, [58, 58, 100]),
            ]},
        },
        [
            {"ty": "gr", "nm": "shadow group",
             "it": [ellipse([52, 11]), fill(BLACK), tr()]},
        ],
    )


def main() -> int:
    animation = {
        "v": "5.7.4", "fr": FPS, "ip": 0, "op": DUR, "w": W, "h": H,
        "nm": "Stryk ball loader", "ddd": 0, "assets": [],
        # Painted front to back.
        "layers": [streaks_layer(), ball_layer(), impact_layer(), shadow_layer()],
        "markers": [],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(animation, separators=(",", ":")))
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {DUR / FPS:.2f}s loop)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
