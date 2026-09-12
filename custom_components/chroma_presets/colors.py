"""Color-science helpers for generating harmonized static light palettes.

Why OKLCH instead of HSL/HSV: HSL's "lightness" is not perceptually uniform -
equal steps in HSL-L look very different in perceived brightness depending on
hue (yellow reads much brighter than blue at the same L). OKLab/OKLCH
(Ottosson, 2020) is built to be perceptually uniform across hues.

Why chroma is gamut-relative, not absolute: every hue has a different maximum
chroma reproducible in sRGB at a given lightness (green/cyan hit the sRGB
gamut wall far earlier than red/violet). Requesting the same absolute OKLCH
chroma for every hue in a scheme means some anchors render at full requested
saturation while others get silently clipped - which is what actually made
earlier palettes look "chaotic": not a flaw in OKLCH itself, but in treating
chroma as hue-independent. Every chroma target here is expressed as a
*fraction of that hue's own gamut ceiling* (see max_chroma_at), so saturation
reads as comparable across hues instead of arbitrary.

Why a secondary-anchor damping factor, not equal chroma everywhere: Ou & Luo's
colour harmony model (2004/2006, CIELAB, 1431 colour pairs judged by human
observers) found two colours at equal high chroma are rated less harmonious
than one dominant saturated colour paired with a more muted one, and that
small lightness gaps between paired colours also reduce harmony. Both
findings are used directly below: `_pick_role_fraction` searches candidate
chroma fractions for non-primary anchors and picks the one that scores best
under `ou_luo_ch` (the Ou-Luo CH formula, reproduced from Ou, Luo, Woodcock &
Wright, "A Colour Design Tool Based on Empirical Studies", DRS 2008, eq. 5),
and TONE_L_STEPS keeps lightness deltas well-separated so consecutive tones
never collapse into a near-identical, low-harmony pair via simultaneous
contrast (Hering's opponent-process colours shift in appearance next to
whatever surrounds them, so tones meant to read as distinct need a real
lightness gap, not just a nominal one).

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


def _max_in_gamut_chroma(L: float, H_deg: float, hi: float = 0.4) -> float:
    """Binary-search the largest OKLCH chroma reproducible in sRGB at L/H.

    This is the per-hue gamut ceiling: the reference point every chroma
    target in this module is expressed as a fraction of, instead of an
    absolute constant that happens to fit some hues and clip others.
    """
    _, a, b = oklch_to_oklab(L, hi, H_deg)
    if _in_gamut(_oklab_to_linear_srgb(L, a, b)):
        return hi

    lo = 0.0
    for _ in range(24):
        mid = (lo + hi) / 2
        _, a, b = oklch_to_oklab(L, mid, H_deg)
        if _in_gamut(_oklab_to_linear_srgb(L, a, b)):
            lo = mid
        else:
            hi = mid
    return lo


def max_chroma_at(L: float, H_deg: float) -> float:
    """Public gamut-ceiling lookup used to turn a chroma *fraction* into an
    actual OKLCH chroma value for a given lightness/hue."""
    return _max_in_gamut_chroma(L, H_deg)


def oklch_to_srgb255(L: float, C: float, H_deg: float):
    """Convert OKLCH to an in-gamut sRGB 0-255 triple.

    If the requested chroma isn't reproducible in sRGB at this L/H, chroma is
    reduced - holding lightness and hue fixed - until it is. Callers in this
    module request gamut-relative chroma already, so this clip should rarely
    trigger; it remains as a safety net for edge cases (e.g. tone steps that
    push L somewhere the precomputed fraction no longer quite fits).
    """
    _, a, b = oklch_to_oklab(L, C, H_deg)
    rgb_lin = _oklab_to_linear_srgb(L, a, b)

    if not _in_gamut(rgb_lin):
        lo = _max_in_gamut_chroma(L, H_deg, hi=C)
        _, a, b = oklch_to_oklab(L, lo, H_deg)
        rgb_lin = _oklab_to_linear_srgb(L, a, b)

    rgb_lin = [max(0.0, min(1.0, c)) for c in rgb_lin]
    srgb = [_linear_to_srgb(c) for c in rgb_lin]
    return tuple(round(c * 255) for c in srgb)


def chroma_from_fraction(L: float, H_deg: float, fraction: float) -> float:
    """Target OKLCH chroma = `fraction` of what's actually reproducible at
    this L/H. Keeps perceived saturation comparable across hues instead of
    requesting a hue-blind absolute chroma that clips unevenly."""
    return max_chroma_at(L, H_deg) * max(0.0, min(1.0, fraction))


# --- CIELAB (D65) + Ou-Luo colour harmony -----------------------------------
# The Ou-Luo model (Ou, Luo, Woodcock & Wright 2004/2006) is defined in
# classic CIELAB, not OKLCH, so scoring needs its own conversion path.

_D65_WHITE = (0.95047, 1.0, 1.08883)


def _linear_srgb_to_xyz(r: float, g: float, b: float):
    x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b
    return x, y, z


def _xyz_to_lab(x: float, y: float, z: float):
    xn, yn, zn = _D65_WHITE

    def f(t):
        return t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29

    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b = 200 * (fy - fz)
    return L, a, b


def rgb255_to_lab(rgb) -> tuple:
    """sRGB 0-255 -> CIELAB (L*, a*, b*), D65 white point."""
    r, g, b = (c / 255 for c in rgb)
    r, g, b = _srgb_to_linear(r), _srgb_to_linear(g), _srgb_to_linear(b)
    x, y, z = _linear_srgb_to_xyz(r, g, b)
    return _xyz_to_lab(x, y, z)


def ou_luo_ch(rgb1, rgb2) -> float:
    """Ou-Luo two-colour harmony score (higher = more harmonious).

    Reproduced from Ou, Luo, Woodcock & Wright, "A Colour Design Tool Based
    on Empirical Studies", DRS 2008, eq. 5 - itself the model from Ou & Luo,
    "A Colour Harmony Model for Two-Colour Combinations", Color Res. Appl.
    31 (2006). Calibrated on flat colour patches on a medium-grey background
    judged by human observers; used here as a heuristic to rank candidate
    chroma/lightness choices against each other, not as an absolute law.
    """
    L1, a1, b1 = rgb255_to_lab(rgb1)
    L2, a2, b2 = rgb255_to_lab(rgb2)

    C1, h1 = math.hypot(a1, b1), math.degrees(math.atan2(b1, a1)) % 360
    C2, h2 = math.hypot(a2, b2), math.degrees(math.atan2(b2, a2)) % 360

    # Metric CIELAB hue difference (Lab units, not degrees): dH*ab = sqrt(dE^2
    # - dL^2 - dC^2), equivalently sqrt(da^2 + db^2 - dC^2) - NOT the raw hue
    # angle difference. Using the angle directly (in degrees) would dwarf the
    # 0.045 coefficient and make HC collapse toward -1 for any distant hues.
    d_c_ab = C1 - C2
    d_hab_sq = (a1 - a2) ** 2 + (b1 - b2) ** 2 - d_c_ab ** 2
    d_hab = math.sqrt(max(0.0, d_hab_sq))
    d_c = math.hypot(d_hab, d_c_ab / 1.46)
    HC = 0.04 + 0.53 * math.tanh(0.8 - 0.045 * d_c)

    Lsum = L1 + L2
    dL = L1 - L2
    HLsum = 0.28 + 0.54 * math.tanh(-3.88 + 0.029 * Lsum)
    HdL = 0.14 + 0.15 * math.tanh(-2 + 0.2 * dL)
    HL = HLsum + HdL

    def h_sy(L, C, hab):
        EC = 0.5 + 0.5 * math.tanh(-2 + 0.5 * C)
        HS = (
            -0.08
            - 0.14 * math.sin(math.radians(hab + 50))
            - 0.07 * math.sin(math.radians(2 * hab + 90))
        )
        t = (90 - hab) / 10
        EY = ((0.22 * L - 12.8) / 10) * math.exp(t - math.exp(t))
        return EC * (HS + EY)

    HH = h_sy(L1, C1, h1) + h_sy(L2, C2, h2)

    return HC + HL + HH


# --- harmony schemes ---------------------------------------------------------
# Each scheme is a set of hue anchors (degrees, relative to a base hue).
# These fixed angular relationships are what "complementary"/"triadic"/etc.
# are defined by - research on harmony (Ou-Luo) says the fixed *chroma* those
# hues are rendered at matters as much as the angle, which is what
# _pick_role_fraction and chroma_from_fraction address; it does not suggest
# the angles themselves are wrong.

ARC_SCHEMES = {
    "monochromatic": 0,
    "analogous": 44,
}

ANCHOR_SCHEMES = {
    "complementary": [0, 180],
    "split_complementary": [0, 150, 210],
    "triadic": [0, 120, 240],
    "tetradic": [0, 90, 180, 270],
}

# Lightness-only tone steps (deltas from the preset's base_l). Chroma is no
# longer part of a tone step's delta - it's re-derived at each step's L from
# that hue's gamut ceiling (see chroma_from_fraction), so a "shade" never
# silently clips on a low-ceiling hue while barely nudging a high-ceiling
# one. Steps are kept well-separated (>= 0.08 apart pairwise) so consecutive
# tones stay distinguishable under simultaneous contrast instead of reading
# as near-duplicates.
TONE_L_STEPS = [0.00, -0.10, 0.10, -0.20, 0.20]

# Candidate chroma fractions tried for non-primary anchors; the one scoring
# highest under ou_luo_ch against the primary anchor's base colour is used
# for every tone step of that anchor. Encodes the Ou-Luo finding that a
# muted secondary reads as more harmonious than a second fully-saturated hue.
_SECONDARY_FRACTION_CANDIDATES = [0.85, 0.7, 0.55, 0.4, 0.28]


def _pick_role_fraction(primary_hue, primary_l, primary_fraction, anchor_hue, base_l):
    """Choose the chroma fraction for a non-primary anchor by picking whichever
    candidate maximizes Ou-Luo CH against the primary anchor's base colour."""
    primary_c = chroma_from_fraction(primary_l, primary_hue, primary_fraction)
    primary_rgb = oklch_to_srgb255(primary_l, primary_c, primary_hue)

    best_fraction, best_score = _SECONDARY_FRACTION_CANDIDATES[0], -math.inf
    for fraction in _SECONDARY_FRACTION_CANDIDATES:
        c = chroma_from_fraction(base_l, anchor_hue, fraction)
        rgb = oklch_to_srgb255(base_l, c, anchor_hue)
        score = ou_luo_ch(primary_rgb, rgb)
        if score > best_score:
            best_score, best_fraction = score, fraction
    return best_fraction


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


def _dedupe_to_srgb(hue_l_frac_triples):
    """Convert (H, L, fraction) triples to unique sRGB, nudging L on any
    collision (chroma is re-derived from the fraction at the nudged L)."""
    used = set()
    colors = []
    for H, L, fraction in hue_l_frac_triples:
        C = chroma_from_fraction(L, H, fraction)
        rgb = oklch_to_srgb255(L, C, H)

        attempt = 0
        while rgb in used and attempt < 12:
            attempt += 1
            sign = 1 if attempt % 2 else -1
            L = min(0.95, max(0.2, L + sign * 0.015 * attempt))
            C = chroma_from_fraction(L, H, fraction)
            rgb = oklch_to_srgb255(L, C, H)

        used.add(rgb)
        colors.append({"rgb": list(rgb), "oklch": [round(L, 3), round(C, 3), round(H % 360, 1)]})

    return colors


def generate_harmony_palette(scheme: str, base_hue: float, base_l: float, chroma_fraction: float, count: int = 25):
    """Generate `count` unique, harmonically-related sRGB colors, already in
    "reveal order": the first N entries are a good-enough palette for a
    target with only N lights, for any N. See van_der_corput (arc schemes)
    and the anchor round-robin below (anchor schemes) for how that's kept
    true regardless of scheme type.

    `chroma_fraction` (0-1) is how close to each hue's own gamut ceiling the
    primary anchor is rendered; non-primary anchors get their own fraction
    chosen by Ou-Luo harmony scoring against the primary (see
    _pick_role_fraction).
    """
    if scheme in ARC_SCHEMES:
        span = ARC_SCHEMES[scheme]
        triples = []
        for i in range(count):
            t = van_der_corput(i) if span else 0.5
            hue_offset = (t - 0.5) * span
            tone_l = TONE_L_STEPS[i % len(TONE_L_STEPS)]
            L = min(0.95, max(0.25, base_l + tone_l))
            triples.append((base_hue + hue_offset, L, chroma_fraction))
        return _dedupe_to_srgb(triples)

    anchors = ANCHOR_SCHEMES[scheme]
    per_anchor = _distribute(count, len(anchors))

    role_fractions = [chroma_fraction]
    for anchor_offset in anchors[1:]:
        role_fractions.append(
            _pick_role_fraction(base_hue, base_l, chroma_fraction, base_hue + anchor_offset, base_l)
        )

    anchor_plans = []
    for anchor_offset, n, fraction in zip(anchors, per_anchor, role_fractions):
        plan = []
        for step in range(n):
            tone_l = TONE_L_STEPS[step % len(TONE_L_STEPS)]
            L = min(0.95, max(0.25, base_l + tone_l))
            plan.append((base_hue + anchor_offset, L, fraction))
        anchor_plans.append(plan)

    # Round-robin across anchors (not grouped by anchor) so a prefix of the
    # result already contains one color per anchor before repeating any.
    interleaved = []
    for i in range(max(len(p) for p in anchor_plans)):
        for plan in anchor_plans:
            if i < len(plan):
                interleaved.append(plan[i])

    return _dedupe_to_srgb(interleaved)
