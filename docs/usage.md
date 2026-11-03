# Using Hearth

Once set up, your Nest appears in Home Assistant as a **Hearth Thermostat**
device, with a climate entity, sensors and, where your Nest supports them,
settings entities.

## Climate card

- **Modes.** Only the modes your equipment actually reports are offered. A
  heat-only system shows Off and Heat.
- **Heating / Idle.** This comes from the Nest's own operating flags, not from
  comparing room temperature with the target.
- **Target temperature.** The Nest stores targets in Celsius, and HA converts
  them for display. Right after you change it, the target may show as
  *assumed*: the Nest has accepted the command but hasn't reported the value
  back yet. The Nest's own report always wins.

## Eco

The Eco preset turns the Nest's manual Eco mode on or off. Choosing **None**
ends manual Eco, but it doesn't disable the Nest's automatic Eco behaviour. Your
Eco temperature limits stay as they are unless you use the separate **Set eco
temperature bounds** action.

## Weekly schedules

Schedules use Home Assistant actions (**Developer tools → Actions**):

1. Run **Hearth: Read weekly schedule**. It returns all seven days in Celsius
   (0 = Monday … 6 = Sunday) and a **revision** number.
2. Run **Hearth: Replace weekly schedule** with the full week you want, the
   temperature unit and that revision.

Hearth saves a private backup of the current schedule before it replaces
anything. If the schedule changed since you read it, the revision won't match
and the replace is refused. Read it again and retry with the new revision.

An empty-looking schedule can still contain hidden continuation entries. Keep
them when you edit.

The schedule's `source` tells you how fresh it is:

| Source | Meaning |
| --- | --- |
| `device` | Read from the Nest during this session |
| `pending` | Your change is queued and the Nest hasn't confirmed it yet |
| `acknowledged` | The Nest confirmed it received that exact version |
| `cache` | Loaded from disk at startup and not refreshed yet |
| `unconfirmed` | A change expired without confirmation. Read again before editing |

Replacing and restoring a schedule has been verified on a real Gen 2.

## Weather

The Nest shows outdoor weather from any HA weather entity you choose:

1. Go to **Settings → Devices & services → Hearth → Configure**.
2. Pick a weather entity.
3. Set the fallback **postal code** and **country** to your actual location.
   The Nest's fallback weather lookup uses these.

If the weather entity is unavailable, the Nest sees no weather. Hearth never
makes up observations.

## Device settings

Switches, numbers and selects appear for settings your Nest actually reports:
learning, Early-On, Sunblock, filter reminders, display and equipment options.
Missing fields stay hidden or unknown.

- **Equipment-affecting entities start disabled.** Enable them yourself in the
  entity settings if you need them.
- The **Set device settings** action changes a group of settings at once.
  Safety and equipment changes need an HA administrator and
  `confirm_equipment_changes: true`. Temperatures are in Celsius.
- Lock PIN hashes are write-only. They're never stored or shown.

Settings have automated test coverage, but not every field has been tried on
real hardware. See [what's tested](compatibility.md) and the
[full settings list](development/device-settings.md).

## Diagnostics

Optional diagnostic entities are disabled by default. Enable them from the
device page: battery voltage, Wi-Fi signal, filter runtime, outdoor
temperature, Sunblock/Early-On activity, heat-pump readiness and time to
target. They're read-only and never change thermostat settings.
