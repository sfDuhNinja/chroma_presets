"""Known bulb capability profiles, keyed by (manufacturer, model) exactly as
reported by Home Assistant's device registry.

Only `has_color` is actually applied (apply_preset uses it to skip
rgb_color on lights that don't support it). Real gamut clamping (e.g.
Philips Hue's Gamut C triangle) already happens automatically in the
device/integration when an rgb_color is sent - duplicating that math here
would just repeat what the firmware already does. `gamut` is kept as a
note for future use, not applied at runtime.

`gamut` research: HA core / hue-python-rgb-converter agree on
(0.6915,0.3038)/(0.17,0.7)/(0.1532,0.0475) for Hue's newer color lights,
including the LCL0xx family Birou/Pat's LCL006 belongs to; IKEA and
Nanoleaf don't publish exact gamut triangles, so those are only
classified qualitatively as narrower or wider than Hue's, going by
community-reported behavior.

Start with the bulbs actually in use (Bucuresti/Dizonaur instance); extend
as new models show up.
"""

DEFAULT_PROFILE = {"has_color": True, "gamut": "wide"}

BULB_PROFILES = {
    ("Signify Netherlands B.V.", "LCL006"): {"has_color": True, "gamut": "wide"},
    ("IKEA of Sweden", "TRADFRI bulb E27 CWS 806lm"): {"has_color": True, "gamut": "narrow"},
    ("IKEA of Sweden", "ORMANAS LED Strip"): {"has_color": True, "gamut": "narrow"},
    ("IKEA of Sweden", "KAJPLATS E14 CWS globe 806lm"): {"has_color": True, "gamut": "narrow"},
    ("Nanoleaf", "NL69"): {"has_color": True, "gamut": "wide"},
    ("IKEA of Sweden", "TRADFRI bulb E27 WS globe 1055lm"): {"has_color": False, "gamut": "none"},
    ("IKEA of Sweden", "Floor lamp WW"): {"has_color": False, "gamut": "none"},
    ("IKEA of Sweden", "KAJPLATS E27 WS globe 1521lm"): {"has_color": False, "gamut": "none"},
    ("IKEA of Sweden", "TRETAKT Smart plug"): {"has_color": False, "gamut": "none"},
    ("Espressif", "esp32-s3-devkitc-1"): {"has_color": False, "gamut": "none"},
}


def get_bulb_profile(manufacturer, model):
    return BULB_PROFILES.get((manufacturer, model), DEFAULT_PROFILE)
