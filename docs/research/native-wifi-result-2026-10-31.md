# First physical native Wi-Fi/HTTPS attempt

After the corrected nine-file install and working UI check, the owner joined the
isolated IoT SSID. The thermostat reported connected, and the owner corroborated
association in the access-point controller. The unwired base produced E22,
which the owner initially could not dismiss, then closed to continue setup.
[Google documents E22 as no power wires detected](https://support.google.com/googlehome/answer/9240096?hl=en).
No wire, jumper, hardware power supply or wiring-check patch was added.

The backend's bounded read-only watch never observed available/state. A failed
ICMP check from the PC is inconclusive across VLANs. HA reported Hearth0.1.0
started with its expected API port published; trusted HTTPS manager GETs succeeded.
Access logging was deliberately disabled, so those checks could not distinguish
an absent request from a rejected native upload.

The owner reconnected USB and performed one fresh protected read-only RAM boot.
It preserved the nine selected files and independently verified backup custody,
plus a partial64-file log capture. All nine installed contents/modes and root
ownership still match; assigned credentials are unchanged. No device write or
native application execution occurred in that diagnostic.

The current native event log contains three relevant HTTPS results for the
configured private backend:

| Native request | HTTP result |
| --- | --- |
| Entry |200 |
| Transport metadata |200 |
| PUT upload |400 |

The event records use the same nine-field layout and status field; normalized
route/status evidence remains private with original frames and independent review.
This demonstrates successful valid HTTPS/assigned authentication for discovery
under the installed native configuration, followed by a refused upload. It does
not prove every TLS-negative case on a physical network, telemetry compatibility,
operational time robustness, command delivery or HVAC behavior. E22 did not stop
all backend requests; its other setup/power effects remain outside this result.

## Bounded rejection diagnostics

HA app0.1.1 adds finite aggregate rejection reason codes to the existing
manager-authenticated device status response, only in native telemetry mode.
Counters are process-local, saturate, and clear on restart. Only fixed reason
labels/counts and the latest label are retained; payloads, field names, credentials,
identifiers, addresses and exception text are not retained. Unknown errors share
one label. Authentication/validation behavior, responses to native requests and
command disabling are unchanged. The normal runtime status shape is unchanged.

New tests cover manager-only access, no counting/parsing before authentication,
secret exclusion, refusal without state mutation, continued valid reporting,
finite keys/count saturation, snapshot isolation and restart reset. make check
passes; the full host suite is855 passed/five optional skips.

The reviewed HA package was staged/read back, and previous source plus the
registry were preserved privately before updating. Supervisor reports0.1.1
started; trusted HTTPS manager diagnostics and unchanged enrollment are verified.
The first immediate readiness probe raced startup and was refused; a later probe
succeeded. No thermostat command or persistent modification occurred. The next
owner-timed native startup will identify the actual upload rejection reason;
the decoder has not been relaxed or declared compatible.
