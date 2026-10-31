# Native UI startup stall after first installation

After the first persistent install passed exact readback and native USB return,
the owner attempted the requested battery-powered, completely unwired-base Wi-Fi
bench. The display remained at the home icon even after an owner restart. The
icon is steady and the LED blinks green. Normal Wi-Fi settings are not reachable.
The backend's private bounded watch recorded no availability or state telemetry.
No native network success or complete application startup is claimed.

[Google's LED guide](https://support.google.com/googlehome/answer/9233319?hl=en)
describes blinking green as startup/restarting/updating. This identifies an
indicator class, not the cause. Since stock software previously reached Wi-Fi
settings on the same unwired base/battery, investigate a possible startup
regression before further connectivity testing. The earlier successful byte
installation and normal USB identity alone were insufficient to establish UI health.

The owner detached the base and reconnected USB; normal USB independently
observed. No further restart or persistent modification has been requested yet.
Prepared diagnostic: original static reader on the unchanged protected snapshot
kernel, capturing current nine files and bounded persistent log tails read-only.
No native code, write-capable kernel, network or raw MTD interface. Source and
operating bounds: [startup diagnostic](../../firmware/startup_diagnostic/README.md).

All eight artifacts reproduce independently. Private profile
file-writer-20261031/startup-diagnostic-v2 and its reproduction are unexecuted;
original build startup-diagnostic-20261031-v2. Earlier unexecuted draft preserved.
Host suite786 passes/five unchanged optional skips; make check passes. No backend
code or HAOS/broker configuration changed during this investigation. Next one
supervised owner-timed read-only diagnostic; actual restoration remains unverified.
