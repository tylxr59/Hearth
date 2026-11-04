# Native device setting contract

Protocol field names are taken from the pinned NLE command contract; code is
original. Bounds below are Hearth validation choices, not claims of measured
support on every model. Values must already have fresh validated native
baselines.

| Field | Type / constraint | Equipment confirmation |
| --- | --- | --- |
| `learning_mode` | boolean | No |
| `preconditioning_enabled` | boolean | No |
| `preconditioning_active` | boolean | Required |
| `sunlight_correction_enabled` | boolean | No |
| `target_humidity_enabled` | boolean | Required |
| `target_humidity` | number 0..100 | Required |
| `temperature_scale` | select C, F | No |
| `time_to_target` | number 0..9007199254740991 | No |
| `time_to_target_training_status` | text | No |
| `fan_timer_duration_minutes` | number 1..720 | No |
| `fan_duty_cycle` | number 0..60 | Required |
| `fan_duty_start_time` | number 0..86399 | Required |
| `fan_duty_end_time` | number 0..86399 | Required |
| `fan_schedule_speed` | select stage1, stage2, stage3 | Required |
| `lower_safety_temp_enabled` | boolean | Required |
| `upper_safety_temp_enabled` | boolean | Required |
| `lower_safety_temp` | number 1.5..35 | Required |
| `upper_safety_temp` | number 24..40 | Required |
| `temp_lock_on` | boolean | Required |
| `temp_lock_pin_hash` | text; write-only, excluded from cache | Required |
| `temp_lock_low_temp` | number 5..35 | Required |
| `temp_lock_high_temp` | number 5..35 | Required |
| `heat_pump_aux_threshold_enabled` | boolean | Required |
| `heat_pump_aux_threshold` | number -40..40 | Required |
| `heat_pump_comp_threshold_enabled` | boolean | Required |
| `heat_pump_comp_threshold` | number -40..40 | Required |
| `equipment_type` | text | Required |
| `heat_source` | text | Required |
| `hot_water_boost_time_to_end` | number 0..9007199254740991 | Required |
| `hot_water_active` | boolean | Required |
| `filter_reminder_enabled` | boolean | No |
| `filter_reminder_level` | number 0..100 | No |
| `postal_code` | text | No |
| `country_code` | text | No |

Fan, heat-pump and hot-water fields require their corresponding reported
capabilities. Paired safety/lock temperatures must remain ordered and fresh.
Controls expire and are never persisted or replayed. State stays reported-only.

Reference:
[NLE command contract](https://github.com/codykociemba/NoLongerEvil-SelfHosted/blob/bca8781012639c1cefc4a08c103fc892158fb630/src/nolongerevil/routes/control/command.py).
