# Native Home Assistant integration

The current deployment target is a native custom integration:

**Nest native client → Hearth's HTTPS listener inside HA Core → HA entities.**

The integration receives the existing native Nest protocol and uses unique
assigned credentials. MQTT and the separate HA app are not part of this path.
The first platform exposes temperature, humidity and target-temperature sensors;
native command delivery and HVAC operation remain unverified and disabled.

## Build and validate

Build a fresh public-source installation directory:

```sh
.venv/bin/python -m tools.package_native_ha build/native-ha
```

Copy the **generated** `custom_components/hearth` directory to HA's configuration
directory. The source template alone is incomplete: the packager includes the
single canonical transport implementation with isolated relative imports. It
excludes the MQTT module, broker credentials, firmware and all private data.

The independent runtime check uses the pinned HA Core2026.10.4 image, a temporary
HA instance and synthetic certificates/credentials, with physical networking
disabled:

```sh
.venv/bin/python -m tools.check_native_ha build/native-ha-check --engine podman
```

Use fresh output paths. No attached thermostat, live HA instance or MQTT broker
is used by that check. Passing it does not establish compatibility with other HA
versions or physical HVAC safety.

## Prepared commissioning profile

The integration loads these owner-only regular files from
`.storage/hearth` under HA's configuration directory:

| File | Purpose |
| --- | --- |
| `profile.json` | Format marker and advertised private-IPv4 HTTPS origin |
| `registry.json` | Existing separate manager/device credential hashes |
| `server.pem` / `server.key` | Native-protocol server certificate and matching key |
| `ca.pem` | The owner CA already installed on the thermostat |

The directory must be0700 and files0600, without symlinks or shared hardlinks.
The listener validates its profile, enrolled-device presence, certificate issuer,
validity, IP SAN and key match. No shared/default credential is generated. The
config entry stores no private keys or device credentials. This experimental
revision requires an independently prepared model-specific commissioning profile;
it is not an automatic installation or credential-extraction feature.

Restart HA after staging a new custom integration, then select **Settings →
Devices & services → Add integration → Hearth** and submit the import form.
Port conflicts or invalid private profiles refuse startup. Entity availability
expires with native state silence; unloading the config entry closes the listener
and cancels its timers. Commands stay disabled.

## This owner's migration

The owner chose HA's IoT address. A certificate signed by the same installed
owner CA covers that address and the previous entry address during handoff,
retaining the server key already proven by the native client. The new transport
origin advertises the IoT address. The old on-device registration URL still needs
its later targeted update; no thermostat flash was required to stage this HA test.

The Hearth MQTT app was stopped at the owner's request. Its seven retained
discovery/state/availability topics were cleared and a fresh subscriber verified
their absence; the old MQTT entity registry entries disappeared. Existing private
source/configuration backups remain for recovery, without a running broker bridge.

Residual Google HTTP connectivity probes and the separate ConnMan time-server
configuration remain an active firmware follow-up. This HA migration does not
claim they are removed. Preserve native control/backplate behavior while preparing
and validating that separate correction.


## Observed native HA activation

The owner explicitly authorized one Core restart, added Hearth, then performed a
fresh normal thermostat startup on the unwired base. The integration's manager
view reports available with temperature/humidity/target-temperature state, and
the owner confirmed all three readings in the native HA device page. HA converts
the native Celsius readings to the user's display units. One initial bucket-shape
request was refused before subsequent uploads succeeded; the decoder remains strict.

The retired Hearth Laboratory app was subsequently uninstalled after its complete
private configuration archive was read back and matched against the active registry
and server key. Its local app source was moved out of the app catalog. The native
integration continues independently, with no MQTT configuration or library bundled.
Google-dependency remediation and native command delivery remain separate unfinished
work; this observation is the read-only native HA milestone.
