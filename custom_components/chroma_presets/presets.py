import asyncio
import json
import logging
import os

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

BASE_PATH = os.path.dirname(os.path.realpath(__file__))

with open(os.path.join(BASE_PATH, "presets.json")) as f:
    PRESET_DATA = json.load(f)


def _get_preset(preset_id):
    for preset in PRESET_DATA.get("presets", []):
        if preset.get("id") == preset_id:
            return preset
    return None


def _select_indices(n_targets, n_colors):
    """Pick which palette indices to hand out to n_targets lights.

    - Fewer lights than colors: take a straight prefix. The palette is
      generated so that its own order is already "reveal order" (round-robin
      across hue anchors, or a low-discrepancy arc sample for
      analogous/monochromatic - see colors.py) - the first N entries are
      already a good, spread-out N-color subset for any N.

      An earlier version picked an evenly-spaced *stride* through the 25
      colors instead (e.g. indices 0, 12, 24 for 3 lights). That looked
      reasonable but ignored the palette's internal structure: for a
      3-anchor scheme, indices 12 spaces apart can all land on multiples of
      the same anchor, handing out 3 colors that are all just tone variants
      of ONE hue instead of one color per anchor - which is exactly why 3
      lights came out looking "too similar" to each other.
    - More lights than colors: wrap around, reusing colors from the start.
    """
    if n_targets <= 0:
        return []
    if n_targets <= n_colors:
        return list(range(n_targets))
    return [i % n_colors for i in range(n_targets)]


def _brightness_for_color(color, base_l, target_brightness):
    """Scale brightness per-light by the color's OKLCH lightness.

    A flat brightness for every bulb regardless of color would throw away the
    tint/shade/tone variation the palette was designed with. Scaling by L
    relative to the preset's base_l keeps that intentional value-scale
    visible in the room instead of flattening every color to the same output
    level.
    """
    l_ratio = (color["oklch"][0] / base_l) if base_l else 1.0
    value = target_brightness * l_ratio
    return int(max(30, min(255, round(value))))


async def apply_preset(hass, preset_id, entity_ids, brightness_override, transition):
    preset = _get_preset(preset_id)
    if preset is None:
        known = ", ".join(p["id"] for p in PRESET_DATA.get("presets", []))
        raise HomeAssistantError(f"Preset '{preset_id}' not found. Known presets: {known}")

    if not entity_ids:
        _LOGGER.warning("chroma_presets.apply_preset: no light entities resolved from targets")
        return

    colors = preset["colors"]
    base_l = preset.get("base_l", 0.6)
    target_brightness = brightness_override or preset.get("brightness", 200)

    indices = _select_indices(len(entity_ids), len(colors))

    tasks = []
    for entity_id, idx in zip(entity_ids, indices):
        color = colors[idx]
        tasks.append(
            hass.services.async_call(
                "light",
                "turn_on",
                {
                    "entity_id": entity_id,
                    "rgb_color": color["rgb"],
                    "brightness": _brightness_for_color(color, base_l, target_brightness),
                    "transition": transition,
                },
                blocking=False,
            )
        )

    await asyncio.gather(*tasks)
