from homeassistant.helpers import device_registry, entity_registry

MAX_GROUP_DEPTH = 4


def ensure_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, str):
        return [data]
    return []


def _expand_group(hass, entity_id, depth=0):
    """Recursively unwrap a light/group entity into individual light entity_ids.

    A group (light group or the older generic `group.*` domain) exposes its
    members via an `entity_id` list attribute. We always unwrap - a group
    target means "these bulbs individually", so each member gets its own
    color from the palette instead of the whole group receiving one flat
    color. (Nested 4+ levels deep is treated as a plain leaf to avoid
    runaway recursion on a misconfigured group loop.)
    """
    if depth > MAX_GROUP_DEPTH:
        return []

    state = hass.states.get(entity_id)
    member_entity_ids = state.attributes.get("entity_id") if state else None

    if not member_entity_ids:
        return [entity_id] if entity_id.startswith("light.") else []

    resolved = []
    for member_id in member_entity_ids:
        resolved.extend(_expand_group(hass, member_id, depth + 1))
    return resolved


def resolve_targets(hass, entity_ids, area_ids, device_ids):
    """Resolve entity_id/area_id/device_id targets down to light entity_ids.

    Areas resolve BOTH entities assigned directly to the area AND entities
    that inherit their area from their parent device - the latter is the
    common case for most paired lights (Zigbee, Matter, Tapo, ...), whose
    entity registry entry usually has no area_id of its own and relies on
    the device's area instead. Missing that path means an area-based target
    silently resolves to nothing, which is exactly what was happening here.

    Kept deliberately simple compared to a full target resolver (no
    floor_id or label_id support yet) - this is a test integration focused
    on the palette/color side, not target resolution. Groups are unwrapped
    into their individual members (see _expand_group).
    """
    entity_reg = entity_registry.async_get(hass)
    device_reg = device_registry.async_get(hass)

    candidates = {e for e in entity_ids if e.startswith(("light.", "group."))}

    def _add_device_entities(device_id, restrict_area_id=None):
        for entry in entity_registry.async_entries_for_device(entity_reg, device_id):
            # If we're pulling this device in because of an area target,
            # don't steal an entity whose own area_id overrides the device's
            # to a *different* area. Direct device targets have no such
            # restriction - if you point at a device, you want all its lights.
            if restrict_area_id is not None and entry.area_id not in (None, restrict_area_id):
                continue
            if entry.entity_id.startswith(("light.", "group.")):
                candidates.add(entry.entity_id)

    for area_id in area_ids:
        for entry in entity_registry.async_entries_for_area(entity_reg, area_id):
            if entry.entity_id.startswith(("light.", "group.")):
                candidates.add(entry.entity_id)

        for device in device_registry.async_entries_for_area(device_reg, area_id):
            _add_device_entities(device.id, restrict_area_id=area_id)

    for device_id in device_ids:
        _add_device_entities(device_id)

    resolved = set()
    for entity_id in candidates:
        resolved.update(_expand_group(hass, entity_id))

    # Sorted for deterministic, reproducible color assignment across calls.
    return sorted(resolved)
