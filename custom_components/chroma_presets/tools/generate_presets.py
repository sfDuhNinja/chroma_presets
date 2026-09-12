#!/usr/bin/env python3
"""Bake presets.json for the Chroma Presets test integration.

This is an offline build step, not something Home Assistant runs. The
integration only ever reads the static presets.json this script produces -
that's the "static" part: no color math happens at apply-time.

Run whenever the palette definitions below change:
    python3 tools/generate_presets.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from colors import generate_harmony_palette  # noqa: E402

OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "presets.json"
)

# base_hue is in OKLCH degrees (not HSL degrees - the wheel is similarly
# ordered red->yellow->green->cyan->blue->magenta but the exact angles for a
# given visual hue differ slightly from HSL/HSV).
PRESET_SPECS = [
    {
        "id": "amber_dusk",
        "name": "Amber Dusk",
        "description": "Cozy analogous palette - ambers, oranges and soft rose for a relaxed evening.",
        "scheme": "analogous",
        "base_hue": 55,
        "base_l": 0.62,
        "chroma_fraction": 0.75,
        "brightness": 160,
    },
    {
        "id": "deep_lagoon",
        "name": "Deep Lagoon",
        "description": "Split-complementary palette - teal and blue with a warm coral accent.",
        "scheme": "split_complementary",
        "base_hue": 215,
        "base_l": 0.58,
        "chroma_fraction": 0.7,
        "brightness": 180,
    },
    {
        "id": "prism_pulse",
        "name": "Prism Pulse",
        "description": "Tetradic palette - a vivid four-hue spread for a lively multicolor look.",
        "scheme": "tetradic",
        "base_hue": 25,
        "base_l": 0.65,
        "chroma_fraction": 0.8,
        "brightness": 200,
    },
]


def main():
    presets = []
    for spec in PRESET_SPECS:
        colors = generate_harmony_palette(
            scheme=spec["scheme"],
            base_hue=spec["base_hue"],
            base_l=spec["base_l"],
            chroma_fraction=spec["chroma_fraction"],
            count=25,
        )
        unique = {tuple(c["rgb"]) for c in colors}
        assert len(unique) == 25, f"{spec['id']}: expected 25 unique colors, got {len(unique)}"

        presets.append(
            {
                "id": spec["id"],
                "name": spec["name"],
                "description": spec["description"],
                "scheme": spec["scheme"],
                "base_l": spec["base_l"],
                "brightness": spec["brightness"],
                "colors": colors,
            }
        )

    with open(OUTPUT_PATH, "w") as f:
        json.dump({"presets": presets}, f, indent=2)
        f.write("\n")

    total_colors = sum(len(p["colors"]) for p in presets)
    print(f"Wrote {len(presets)} presets ({total_colors} colors total) to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
