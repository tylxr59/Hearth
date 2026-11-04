# What's tested

Hearth keeps three kinds of evidence separate: **tested on a real Nest**,
**tested in simulation or automated tests only**, and **not tested**. A
feature showing up in Home Assistant doesn't mean it has been verified on real
hardware.

All real-hardware results come from one unit: a **Gen 2, Display-2.6, software
5.9.4-5**, wired to an oil-fired baseboard heating system.

| Feature | Real Nest | Still to do |
| --- | --- | --- |
| Temperature/humidity readings in HA | ✅ Working | Multi-day reliability |
| Target temperature changes | ✅ 63 → 62 → 63 °F confirmed on the dial | Native value echo back to HA |
| Eco on/off | ✅ Confirmed on the device | Other configurations |
| Weekly heat schedule | ✅ Replace, read back, backup and restore of the original | A real timed schedule change; other modes |
| Weather from HA | ✅ Nest requests served, timezone correct | Every forecast field on the Nest's screen |
| Local time | ✅ Corrected local time on the Nest | — |
| Choosing your own time server | ✅ Writer completed and passed readback/encoding checks | Confirm time-service behaviour after reboot |
| Device settings | 🧪 Automated and HA-sandbox tests | Each field on a real unit |
| Actually switching the furnace on/off | ❌ Not tested | A supervised heating cycle |
| Cooling, fan, ranges, emergency heat | 🧪 Simulation only | Suitable real equipment |
| Power cut / HA outage behaviour | 🧪 No-replay tests | A real outage and return |
| Full flash backup | ✅ Two passes, cross-checked offline | — |
| Originals extracted from the full backup | ✅ Worked on one real backup; a later backup refused one damaged settings fragment, so the wizard now falls back to reading from the Nest | An install that uses backup-extracted originals |
| Space check and both install phases in one RAM boot | ✅ Capacity and both separately approved installs passed in one boot | Guided restore; complete reduced-boot wizard |
| Return to USB boot mode without pressing the ring | ✅ Software restart and successor loader transfer without another ring press | Successor readiness and completed install |
| Saved-file restore | ✅ Back to the stock home screen | — |
| Full-chip restore | ❌ Not tested, no tool for it | — |
| Full wizard on a stock Nest | ❌ Not run end to end | One supervised stock install and restore |
| Other models / software / Gen 1 / Gen 3 | ❌ Not supported | Their own measured profiles |

✅ verified on hardware · 🧪 automated/simulated only · ❌ not done
