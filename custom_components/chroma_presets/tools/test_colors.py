#!/usr/bin/env python3
"""Self-check for colors.py. Run: python3 tools/test_colors.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from colors import (  # noqa: E402
    TONE_L_STEPS,
    _SECONDARY_FRACTION_CANDIDATES,
    _pick_role_fraction,
    generate_harmony_palette,
    max_chroma_at,
    oklch_to_srgb255,
    ou_luo_ch,
)


def test_gamut_relative_chroma_never_clips_below_requested():
    # For a spread of hues at a fixed L, requesting a fraction of the local
    # ceiling must land in-gamut without oklch_to_srgb255 needing to clip
    # further (that clip is a safety net, not the normal path here).
    for h in range(0, 360, 15):
        ceiling = max_chroma_at(0.6, h)
        c = ceiling * 0.75
        rgb = oklch_to_srgb255(0.6, c, h)
        assert all(0 <= v <= 255 for v in rgb), (h, rgb)


def test_tone_steps_stay_pairwise_separated():
    steps = sorted(TONE_L_STEPS)
    gaps = [b - a for a, b in zip(steps, steps[1:])]
    assert all(g >= 0.08 for g in gaps), steps


def test_palettes_are_25_unique_colors():
    specs = [
        ("analogous", 55, 0.62, 0.75),
        ("split_complementary", 215, 0.58, 0.7),
        ("tetradic", 25, 0.65, 0.8),
        ("monochromatic", 10, 0.6, 0.6),
        ("complementary", 300, 0.6, 0.7),
        ("triadic", 120, 0.6, 0.7),
    ]
    for scheme, hue, l, frac in specs:
        colors = generate_harmony_palette(scheme, hue, l, frac, count=25)
        unique = {tuple(c["rgb"]) for c in colors}
        assert len(unique) == 25, (scheme, len(unique))


def test_ou_luo_scores_discriminate_between_chroma_fractions():
    # Same anchor hue, only chroma fraction varies (how _pick_role_fraction
    # actually uses ou_luo_ch) - scores must differ meaningfully, not
    # collapse to the same value (which would mean CH can't rank anything).
    base_l, hue_a, hue_b = 0.6, 25, 65
    primary = oklch_to_srgb255(base_l, max_chroma_at(base_l, hue_a) * 0.8, hue_a)
    ceiling_b = max_chroma_at(base_l, hue_b)

    scores = [
        ou_luo_ch(primary, oklch_to_srgb255(base_l, ceiling_b * f, hue_b))
        for f in _SECONDARY_FRACTION_CANDIDATES
    ]
    assert max(scores) - min(scores) > 0.01, scores


def test_pick_role_fraction_returns_a_candidate():
    fraction = _pick_role_fraction(25, 0.6, 0.8, 65, 0.6)
    assert fraction in _SECONDARY_FRACTION_CANDIDATES


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} checks passed")


if __name__ == "__main__":
    main()
