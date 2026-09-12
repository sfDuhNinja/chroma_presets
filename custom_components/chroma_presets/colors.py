"""Color-science helpers for generating harmonized static light palettes.

Why OKLCH instead of HSL/HSV: HSL's "lightness" is not perceptually uniform -
equal steps in HSL-L look very different in perceived brightness depending on
hue (yellow reads much brighter than blue at the same L). That's the
Helmholtz-Kohlrausch effect, and it's exactly why a naive HSV-based palette
generator produces sets where some bulbs "pop" and others look dim even
though the numbers say they shouldn't. OKLab/OKLCH (Ottosson, 2020) is built
to be perceptually uniform across hues, so holding L constant across a
palette keeps perceived lightness consistent, and varying it deliberately
(see TONE_STEPS below) produces an intentional tint/shade/tone spread instead
of an accidental one.

This module is only used offline by tools/generate_presets.py to bake
presets.json. Nothing here runs at Home Assistant runtime.
"""

import math

# --- sRGB <-> linear sRGB ---------------------------------------------------

def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


# --- linear sRGB <-> OKLab ---------------------------------------------------
# Constants from https://bottosson.github.io/posts/oklab/

def _cbrt(x: float) -> float:
    return math.copysign(abs(x) ** (1 / 3), x)


def _oklab_to_linear_srgb(L: float, a: float, b: float):
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b

    l = l_ ** 3
    m = m_ ** 3
    s = s_ ** 3

    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return r, g, bb


# --- OKLCH <-> OKLab ---------------------------------------------------------

def oklch_to_oklab(L: float, C: float, H_deg: float):
    H = math.radians(H_deg)
    return L, C * math.cos(H), C * math.sin(H)


# --- gamut mapping + sRGB byte output ---------------------------------------

def _in_gamut(rgb_lin, eps=1e-4) -> bool:
    return all(-eps <= c <= 1 + eps for c in rgb_lin)


def oklch_to_srgb255(L: float, C: float, H_deg: float):
    """Convert OKLCH to an in-gamut sRGB 0-255 triple.

    If the requested chroma isn't reproducible in sRGB at this L/H, chroma is
    reduced - holding lightness and hue fixed - until it is. That keeps the
    hue relationship a palette was designed around intact, instead of
    letting an out-of-gamut color silently clip to something else (which
    would quietly break the harmony scheme).
    """
    _, a, b = oklch_to_oklab(L, C, H_deg)
    rgb_lin = _oklab_to_linear_srgb(L, a, b)

    if not _in_gamut(rgb_lin):
        lo, hi = 0.0, C
        for _ in range(24):
            mid = (lo + hi) / 2
            _, a2, b2 = oklch_to_oklab(L, mid, H_deg)
            trial = _oklab_to_linear_srgb(L, a2, b2)
            if _in_gamut(trial):
                lo = mid
            else:
                hi = mid
        _, a, b = oklch_to_oklab(L, lo, H_deg)
        rgb_lin = _oklab_to_linear_srgb(L, a, b)

    rgb_lin = [max(0.0, min(1.0, c)) for c in rgb_lin]
    srgb = [_linear_to_srgb(c) for c in rgb_lin]
    return tuple(round(c * 255) for c in srgb)


# --- harmony schemes ---------------------------------------------------------
# Each scheme is a set of hue anchors (degrees, relative to a base hue) plus a
# jitter range: how far each anchor may be locally spread to add variety
# without breaking the relationship the scheme is named for.

# Two families of scheme, because they need fundamentally different treatment:
#
# ARC_SCHEMES sample a single continuous hue arc. "analogous" is *defined* as
# a compact family of neighboring hues - the span here (44 degrees total) is
# what actually keeps it looking like one family. The earlier version spread
# 3 anchors 30 degrees apart and then let each wobble +-12 degrees on top of
# that, for an 84-degree total range - wide enough that the outer edge (e.g.
# base_hue=55 - 42 = 13 degrees) crossed clean out of "amber" into "pink".
# That was the amber_dusk bug: a light landing on that edge got a rose/salmon
# color instead of an amber one.
ARC_SCHEMES = {
    "monochromatic": 0,
    "analogous": 44,
}

# ANCHOR_SCHEMES use exact, fixed hue anchors - complementary/triadic/tetradic
# are *defined* by a precise angular relationship, so the anchors don't jitter
# at all here (unlike the earlier version). All depth/variety comes from
# TONE_STEPS (lightness/chroma), not from wobbling the hue - a wobble big
# enough to add visible variety is also big enough to blur the relationship
# the scheme is named for.
ANCHOR_SCHEMES = {
    "complementary": [0, 180],
    "split_complementary": [0, 150, 210],
    "triadic": [0, 120, 240],
    "tetradic": [0, 90, 180, 270],
}

# Tone steps applied cyclically, as (lightness, chroma) deltas from the
# preset's base L/C. Gives each hue a tint/shade/tone spread (a real
# value-scale, like a paint swatch strip) instead of one flat color repeated.
TONE_STEPS = [
    (0.00, 0.00),
    (-0.10, -0.02),
    (0.08, -0.04),
    (-0.04, 0.03),
    (0.04, 0.02),
]


def van_der_corput(index: int, base: int = 2) -> float:
    """Low-discrepancy 1D sequence in [0, 1).

    The point of this (over a plain linear sweep) is that ANY prefix of
    consecutive indices is already spread evenly across the range - e.g. for
    base 2: 0, 0.5, 0.25, 0.75, 0.125, ... First 2 values bracket the range,
    first 4 quarter it, etc. That's what a small room (fewer bulbs than the
    palette has colors) needs: taking the first N palette entries should
    already cover the arc, not bunch near one edge of it.
    """
    vdc, denom = 0.0, 1
    n = index
    while n:
        denom *= base
        n, remainder = divmod(n, base)
        vdc += remainder / denom
    return vdc


def _distribute(count: int, n_buckets: int):
    """Split `count` items across `n_buckets` as evenly as possible."""
    base, extra = divmod(count, n_buckets)
    return [base + (1 if i < extra else 0) for i in range(n_buckets)]


def _dedupe_to_srgb(hue_l_c_triples):
    """Convert (H, L, C) triples to unique sRGB, nudging L on any collision."""
    used = set()
    colors = []
    for H, L, C in hue_l_c_triples:
        rgb = oklch_to_srgb255(L, C, H)

        attempt = 0
        while rgb in used and attempt < 12:
            attempt += 1
            sign = 1 if attempt % 2 else -1
            L = min(0.95, max(0.2, L + sign * 0.015 * attempt))
            rgb = oklch_to_srgb255(L, C, H)

        used.add(rgb)
        colors.append({"rgb": list(rgb), "oklch": [round(L, 3), round(C, 3), round(H % 360, 1)]})

    return colors


def generate_harmony_palette(scheme: str, base_hue: float, base_l: float, base_c: float, count: int = 25):
    """Generate `count` unique, harmonically-related sRGB colors, already in
    "reveal order": the first N entries are a good-enough palette for a
    target with only N lights, for any N. See van_der_corput (arc schemes)
    and the anchor round-robin below (anchor schemes) for how that's kept
    true regardless of scheme type.
    """
    if scheme in ARC_SCHEMES:
        span = ARC_SCHEMES[scheme]
        triples = []
        for i in range(count):
            t = van_der_corput(i) if span else 0.5
            hue_offset = (t - 0.5) * span
            tone_l, tone_c = TONE_STEPS[i % len(TONE_STEPS)]
            L = min(0.95, max(0.25, base_l + tone_l))
            C = max(0.0, base_c + tone_c)
            triples.append((base_hue + hue_offset, L, C))
        return _dedupe_to_srgb(triples)

    anchors = ANCHOR_SCHEMES[scheme]
    per_anchor = _distribute(count, len(anchors))

    anchor_plans = []
    for anchor_offset, n in zip(anchors, per_anchor):
        plan = []
        for step in range(n):
            tone_l, tone_c = TONE_STEPS[step % len(TONE_STEPS)]
            L = min(0.95, max(0.25, base_l + tone_l))
            C = max(0.0, base_c + tone_c)
            plan.append((base_hue + anchor_offset, L, C))
        anchor_plans.append(plan)

    # Round-robin across anchors (not grouped by anchor) so a prefix of the
    # result already contains one color per anchor before repeating any.
    interleaved = []
    for i in range(max(len(p) for p in anchor_plans)):
        for plan in anchor_plans:
            if i < len(plan):
                interleaved.append(plan[i])

    return _dedupe_to_srgb(interleaved)
