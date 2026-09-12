"""Known bulb capability profiles, keyed by (manufacturer, model) exactly as
reported by Home Assistant's device registry.

Only `has_color` is actually applied (apply_preset uses it to skip
rgb_color on lights that don't support it). Real gamut clamping (e.g.
Philips Hue's Gamut C triangle) already happens automatically in the
device/integration when an rgb_color is sent - duplicating that math here
would just repeat what the firmware already does. `gamut` and
`max_lumens` are kept as notes for future use, not applied at runtime.

`gamut` research: HA core / hue-python-rgb-converter agree on
(0.6915,0.3038)/(0.17,0.7)/(0.1532,0.0475) for Hue's newer color lights,
including the LCL0xx family Birou/Pat's LCL006 belongs to; IKEA and
Nanoleaf don't publish exact gamut triangles, so those are only
classified qualitatively as narrower or wider than Hue's, going by
community-reported behavior.

`max_lumens` is the manufacturer-rated output, where published - it's
where the model name states it (e.g. "806lm"), or the well-documented
spec sheet figure otherwise. `null` means no figure could be verified;
it is NOT a placeholder for "dim" (a bulb like LCL006 may well be bright,
the number just isn't publicly confirmed). Home Assistant's `brightness`
attribute is already relative to each device's own maximum, so this
number isn't needed to normalize brightness across mixed bulbs - it's
just useful context (e.g. deciding how many lights of what wattage to
point at one preset for a target overall room brightness).

Start with the bulbs actually in use (Bucuresti/Dizonaur instance); extend
as new models show up.
"""

DEFAULT_PROFILE = {"has_color": True, "gamut": "wide", "max_lumens": None}

BULB_PROFILES = {
    ("Signify Netherlands B.V.", "LCL006"): {"has_color": True, "gamut": "wide", "max_lumens": None},
    ("IKEA of Sweden", "TRADFRI bulb E27 CWS 806lm"): {"has_color": True, "gamut": "narrow", "max_lumens": 806},
    ("IKEA of Sweden", "ORMANAS LED Strip"): {"has_color": True, "gamut": "narrow", "max_lumens": None},
    ("IKEA of Sweden", "KAJPLATS E14 CWS globe 806lm"): {"has_color": True, "gamut": "narrow", "max_lumens": 806},
    ("Nanoleaf", "NL69"): {"has_color": True, "gamut": "wide", "max_lumens": 1100},
    ("IKEA of Sweden", "TRADFRI bulb E27 WS globe 1055lm"): {"has_color": False, "gamut": "none", "max_lumens": 1055},
    ("IKEA of Sweden", "Floor lamp WW"): {"has_color": False, "gamut": "none", "max_lumens": None},
    ("IKEA of Sweden", "KAJPLATS E27 WS globe 1521lm"): {"has_color": False, "gamut": "none", "max_lumens": 1521},
    ("IKEA of Sweden", "TRETAKT Smart plug"): {"has_color": False, "gamut": "none", "max_lumens": None},
    ("Espressif", "esp32-s3-devkitc-1"): {"has_color": False, "gamut": "none", "max_lumens": None},
}


def get_bulb_profile(manufacturer, model):
    return BULB_PROFILES.get((manufacturer, model), DEFAULT_PROFILE)
