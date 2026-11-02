# Compatibility and evidence

| Capability | Real device result | Remaining scope |
| --- | --- | --- |
| Gen2 Display-2.6, primary5.9.4-5 | Installed, native UI works | Other models/versions unsupported |
| Local telemetry and HA climate | Working | Multi-day reliability |
| Single target |63→62→63F and matching HA acknowledgement | Explicit native echo is separate |
| Manual Eco | On/off confirmed by device mode and restored physically | Other configurations and bound writes |
| Weekly HEAT schedule | Future point, correct readback, ACK, backups, original restore | Actual timed execution and other modes |
| Weather | Native requests served, timezone correct | Full physical forecast-view verification |
| New device settings | Host/native-protocol and HA sandbox tests | Per-field actual-unit validation |
| Actual HVAC switching | Not measured | Identify equipment and supervise a complete cycle |
| Cooling, fan, range, emergency heat | Synthetic coverage | Appropriate real hardware |
| Outage/restart behavior | No-intent-replay tests | Supervised actual outage/return and sustained use |
| Installer | Guided checked-profile frontend | Automatic acquisition/per-unit build and fresh-unit validation |
| Recovery | Selected original files restored and native UI recovered | Whole-firmware and hardware power-loss recovery |

Do not use the feature list as a claim that all equipment or a stock-unit public
installer has been validated. Gen1 remains a research target.
