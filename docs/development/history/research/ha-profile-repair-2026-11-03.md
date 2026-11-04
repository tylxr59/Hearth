# Matching HA profile restored, 2026-11-03

After the successful combined Nest install, the owner reported no Hearth entry
in HA. Authenticated read-only checks confirmed zero Hearth configuration
entries and no active Hearth profile directory. HACS had v0.11.1 installed.
Earlier assertions of entry preservation were too strong: the saved bundle had
been matched to the device, but live entry existence had not been checked.

Read-only SSH inspection found preserved profile backups. Exactly one matched
the installed Nest's device credential, CA, endpoint and commissioning bundle.
Its server key, certificate chain, dates and address coverage passed checks.
Copies of the evidence remain private. No credential values or private keys
were printed or committed.

The owner explicitly approved restoring that exact profile and registering the
missing entry. The restore verified all nine source-file digests before and
after copying into a fresh private stage, then moved the stage to the absent
active path without overwriting an existing profile. The saved backup remains
intact. The installed config flow's existing-profile branch presented an empty
schema; submitting it registered the entry without generating credentials.

HA reported one loaded Hearth entry and 38 registered entities. Its live
commissioning bundle exactly matches the bundle used for the installed Nest.
An HTTPS request from the HA network verified the listener's CA and hostname
and received the expected unauthenticated refusal. No HA Core restart, HACS
code change, Nest write, HVAC call or credential rotation occurred.

At the first observation, the enabled entities were unavailable and diagnostics
showed no Nest reports or authentication rejections. A later unauthenticated
listener test can itself add a rejection and must not be attributed to the
Nest. The owner's current display/USB state and fresh readings remain pending.
Registration success is not device connectivity validation.

## Final owner-supervised observation

The owner approved reattaching the display to the real wired heating base,
then confirmed the normal temperature dial and fresh HA readings. A bounded
read-only HA observation saw availability return and both temperature and
humidity become available, with a native request age of 9.7 seconds, no
authentication rejections and no pending control intents. No control command
was sent and no heating start/stop test was performed. This completes the
post-install return and readings check; outage reliability remains unmeasured.
