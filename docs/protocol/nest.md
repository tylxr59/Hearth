# Protocol boundaries

## Canonical laboratory API (new, not stock Nest)

All requests outside localhost require HTTPS. Request bodies are JSON with duplicate keys and non-finite numbers rejected; maximum body 16 KiB. No credentials in URLs. Device Basic username is the exact uppercase alphanumeric serial, optionally prefixed `nest.`; password is the 64 hex character unique credential. Header/query serial claims alone never authenticate.

| Method/path | Role | Behavior |
|---|---|---|
| POST `/v1/device/state` | device | Validates/merges its own state, refreshes availability. |
| GET `/v1/device/commands` | device | Pending requests with stable IDs; no implicit applied-state claim. |
| POST `/v1/device/ack` | device | Array of up to three command IDs; removes acknowledged requests. |
| GET `/v1/manage/devices` | manager Bearer | Redacted diagnostics, states, availability, capabilities. |
| POST `/v1/manage/devices/{serial}` | manager | Explicit enrollment with capabilities; generates/returns credential once; rejects duplicates. |
| PUT same path | manager | Generates a replacement credential; invalidates the old one and clears volatile data. |
| DELETE same path | manager | Revocation; clears volatile device data. |
| POST `/v1/manage/devices/{serial}/commands` | manager | Same command validator used by MQTT. |

State keys: temperature (-40..80°C telemetry), target_temperature (5..35°C telemetry), humidity (0..100), configured mode, action (off/idle/heating/cooling/fan), optional configured fan, bounded version string. Telemetry ranges are sanity checks, not established hardware safety limits. Control is more conservative: temperature **10..30°C**, configured mode from off/heat/cool, fan auto/on only if explicitly enabled. Heat-cool ranges, presets, away and schedules are unsupported.

Commands: `{"operation":"temperature","value":22.5}`; mode/fan use string values. At most one pending request per operation, latest request supersedes earlier intent. TTL is 30 monotonic seconds, availability 90 seconds after last state report. All state/intent is lost at restart. Clock wall-time changes do not prolong queues. A future bridge must apply each ID at most once, report measured/applied state and acknowledge; expiration does not undo an already applied setpoint. Exactly-once physical actuation across device power loss is not provided.

Credential registry edits through the API persist immediately. Offline CLI edits require stopping and restarting the backend; do not edit its registry concurrently. There is no auto-enrollment or open bootstrap listener.

## Observed legacy Nest protocol

Pinned NLE source supplies entry URLs and handles PUT/subscribe with `objects`, `object_key`, `value`, object_revision/object_timestamp, client session and conditional-write fields. It accepts additional historical shapes. Real authentication names may also use `d.SERIAL.random`; Hearth intentionally does not interpret those as credentials without a validated bootstrap design.

Offline review of the recovered 5.9.4-5 client now corroborates assigned credential settings and Basic-auth builders. The response header `X-nl-set-client-credentials` updates the ID/secret separately; the reviewed helper logs both and a 401 can select default credentials. None of this supplies trusted enrollment, atomic rotation or a durable rollback procedure. Header delivery and the private logging-removal candidate remain unvalidated on target. See [native bootstrap review](../research/native-bootstrap-2026-10-30.md). No such header is emitted or accepted as an enrollment/rotation request by Hearth.

The opt-in test factory flag `experimental_nest=True` mounts `/nest/entry`, `/nest/transport/put` and `/nest/transport/v7/put`. The normal CLI/container does not enable them. It accepts only an `objects` array of up to two buckets with exactly object_key/value. Own `device.SERIAL` permits current_temperature/current_humidity/software_version; own `shared.SERIAL` permits target_temperature/target_temperature_type. Unknown buckets, fields, other serials and ambiguous data are rejected. All objects validate before state mutation. Replies contain no merged-state echo.

This strict fixture decoder is **not a complete Nest transport implementation**. Revision/CAS handling, chunked long-poll subscribe, pairing buckets, sleep headers, native authentication bootstrap and command mapping are not implemented. Empty PUT responses have not been verified on a device. No assumption that raw Nest action/fan fields match canonical state is made.

The [native wire review](../research/native-protocol-2026-10-30.md) corroborates
response revision/timestamp-before-key ordering and flags a preliminary
brace-counting extractor. Full buffering, CAS and subscription semantics remain
unverified. The next target measurement is an isolated TLS callback test, not
activation of these partial routes.

## MQTT

Discovery topic `homeassistant/climate/hearth_SERIAL/config`; state `hearth/SERIAL/state`, availability `hearth/SERIAL/availability` plus bridge last-will `hearth/bridge/availability`. Only offline availability is retained; online status is a live five-second heartbeat, avoiding stale retained online markers across broker restart. MQTT v5 subscription preserves retain flags and suppresses old retained command delivery. Retained live commands, unknown paths, arbitrary raw fields, oversized payloads, invalid UTF-8, booleans-as-temperature, non-finite values and unsupported operations fail closed. No offline broker session queue is requested. HA commands are non-retained. See [official MQTT climate schema](https://www.home-assistant.io/integrations/climate.mqtt/) and [broker ACL](../../homeassistant/mosquitto.acl).

The broker authenticates command publishers; payloads do not carry redundant device credentials. Broker compromise or a writer with broad ACLs can control enrolled devices within allowed operations. Use one backend instance per namespace/client ID. Firmware capabilities must come from bench validation; simulation defaults are not hardware detection.
