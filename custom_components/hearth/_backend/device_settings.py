"""Original typed contract for native device settings; no relay/control-loop logic.

Field names are protocol compatibility identifiers from the pinned NLE reference.
Values are constrained independently here. Settings have no invented defaults.
"""

import re
from dataclasses import dataclass

from .validation import Invalid, number


@dataclass(frozen=True)
class Setting:
    kind: str
    label: str
    low: float = 0
    high: float = 0
    options: tuple = ()
    equipment: bool = False
    sensitive: bool = False


SETTINGS = {
    "learning_mode": Setting("boolean", "Auto-Schedule"),
    "preconditioning_enabled": Setting("boolean", "Early-On"),
    "preconditioning_active": Setting("boolean", "Preconditioning", equipment=True),
    "sunlight_correction_enabled": Setting("boolean", "Sunblock"),
    "target_humidity_enabled": Setting("boolean", "Humidity control", equipment=True),
    "target_humidity": Setting("number", "Target humidity", 0, 100, equipment=True),
    "temperature_scale": Setting("select", "Temperature units", options=("C", "F")),
    "time_to_target": Setting("number", "Time to target timestamp", 0, 9007199254740991),
    "time_to_target_training_status": Setting("text", "Time to target training"),
    "fan_timer_duration_minutes": Setting("number", "Fan timer duration", 1, 720),
    "fan_duty_cycle": Setting("number", "Fan minutes per hour", 0, 60, equipment=True),
    "fan_duty_start_time": Setting("number", "Fan schedule start", 0, 86399, equipment=True),
    "fan_duty_end_time": Setting("number", "Fan schedule end", 0, 86399, equipment=True),
    "fan_schedule_speed": Setting(
        "select", "Fan schedule speed", options=("stage1", "stage2", "stage3"), equipment=True
    ),
    "lower_safety_temp_enabled": Setting(
        "boolean", "Low safety temperature enabled", equipment=True
    ),
    "upper_safety_temp_enabled": Setting(
        "boolean", "High safety temperature enabled", equipment=True
    ),
    "lower_safety_temp": Setting("number", "Low safety temperature", 1.5, 35, equipment=True),
    "upper_safety_temp": Setting("number", "High safety temperature", 24, 40, equipment=True),
    "temp_lock_on": Setting("boolean", "Temperature lock", equipment=True),
    "temp_lock_pin_hash": Setting(
        "text", "Temperature lock PIN hash", sensitive=True, equipment=True
    ),
    "temp_lock_low_temp": Setting("number", "Lock lower temperature", 5, 35, equipment=True),
    "temp_lock_high_temp": Setting("number", "Lock upper temperature", 5, 35, equipment=True),
    "heat_pump_aux_threshold_enabled": Setting(
        "boolean", "Aux heat threshold enabled", equipment=True
    ),
    "heat_pump_aux_threshold": Setting("number", "Aux heat threshold", -40, 40, equipment=True),
    "heat_pump_comp_threshold_enabled": Setting(
        "boolean", "Compressor threshold enabled", equipment=True
    ),
    "heat_pump_comp_threshold": Setting("number", "Compressor threshold", -40, 40, equipment=True),
    "equipment_type": Setting("text", "Equipment type", equipment=True),
    "heat_source": Setting("text", "Heat source", equipment=True),
    "hot_water_boost_time_to_end": Setting(
        "number", "Hot water boost end", 0, 9007199254740991, equipment=True
    ),
    "hot_water_active": Setting("boolean", "Hot water", equipment=True),
    "filter_reminder_enabled": Setting("boolean", "Filter reminders"),
    "filter_reminder_level": Setting("number", "Filter reminder level", 0, 100),
    "postal_code": Setting("text", "Postal code"),
    "country_code": Setting("text", "Country code"),
}


def validate(name, value):
    if name not in SETTINGS:
        raise Invalid("unsupported device setting")
    spec = SETTINGS[name]
    if spec.kind == "boolean":
        if type(value) is not bool:
            raise Invalid("device setting requires a boolean")
    elif spec.kind == "number":
        number(value, spec.low, spec.high)
    elif spec.kind == "select":
        if not isinstance(value, str) or value not in spec.options:
            raise Invalid("unsupported setting option")
    elif not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9 ._+-]{1,64}", value) is None:
        raise Invalid("bounded device setting text required")
    if name == "country_code" and re.fullmatch(r"[A-Z]{2}", value) is None:
        raise Invalid("two-letter uppercase country code required")
    if name == "temp_lock_pin_hash" and re.fullmatch(r"[0-9a-fA-F]{32,64}", value) is None:
        raise Invalid("precomputed native PIN hash required")
    return value


def plan(native, ident, value):
    if (
        not isinstance(value, dict)
        or set(value) - {"settings", "confirm_equipment_changes"}
        or "settings" not in value
    ):
        raise Invalid("settings object required")
    settings = value["settings"]
    if not isinstance(settings, dict) or not settings or len(settings) > len(SETTINGS):
        raise Invalid("bounded nonempty settings required")
    if type(value.get("confirm_equipment_changes", False)) is not bool:
        raise Invalid("equipment confirmation must be boolean")
    clean = {name: validate(name, item) for name, item in settings.items()}
    current = native.reported.get(ident, {}).get("device", {}).get("values", {})
    record = native._records_for(ident).get(f"device.{ident}")
    restored = native.restored_fields.get(ident, set())
    for name in clean:
        spec = SETTINGS[name]
        if spec.equipment and value.get("confirm_equipment_changes") is not True:
            raise Invalid("equipment-affecting settings require explicit confirmation")
        if record is None or name not in record.fingerprints or ("device", name) in restored:
            raise Invalid("fresh device setting baseline required")
        if not spec.sensitive:
            if name not in current:
                raise Invalid("validated device setting baseline required")
            validate(name, current[name])
        if name.startswith("fan_") and not native.capabilities(ident)["fan"]:
            raise Invalid("fan setting requires reported fan capability")
        if name.startswith("heat_pump_") and current.get("heatpump_ready") is not True:
            raise Invalid("heat pump setting requires reported heat pump capability")
        if name.startswith("hot_water_") and current.get("has_hot_water_control") is not True:
            raise Invalid("hot water setting requires reported capability")
    merged = current | clean
    for low, high in (
        ("lower_safety_temp", "upper_safety_temp"),
        ("temp_lock_low_temp", "temp_lock_high_temp"),
    ):
        if clean.keys() & {low, high} and (
            low not in merged
            or high not in merged
            or merged[low] >= merged[high]
            or ("device", low) in restored
            or ("device", high) in restored
        ):
            raise Invalid("ordered fresh paired temperature baseline required")
    first = next(iter(clean))
    return "device", first, clean[first], {k: v for k, v in clean.items() if k != first}
