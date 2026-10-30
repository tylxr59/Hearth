# Outstanding work

Release-blocking:

- Identity intake and authorized ROM enumeration complete: enclosure `02A`, reported `Display-2.6`, firmware `5.9.4-5`, normal USB `2464:0002`, brief OMAP `0451:d00e` during restart; see docs/research/device-intake-2026-10-30.md. Obtain base/board identity and reviewed Gen 2 firmware acquisition/MTD/boot/recovery evidence. No payload was sent. Actual nlclient/osm binaries remain unavailable; static configuration is not API evidence.
- Determine reliable local IPC control feasibility; revise ADR if an on-device bridge is justified. No bridge currently exists.
- Verify private CA, hostname/time checks and unique stock-client credential installation; design safe bootstrap and rollback. No plaintext production fallback.
- Implement/validate full native entry, pairing and revision/CAS/chunked subscribe transport, with power/schedule regression fixtures, or replace it with a verified local bridge. Experimental decoder is incomplete and default-disabled.
- Build a revision-specific bootable firmware image and complete service hardening profile; current artifacts are inert review bundles and partial offline replacements only.
- Establish recovery before any authorized write. No flash/provision apply command exists and no device service verification has been performed.
- Implement/test device firewall compatible with measured kernel/tools; external VLAN restrictions are mandatory in the interim.
- Complete separately authorized dummy-load HVAC regulation, native scheduling, protective behavior, restart/power, sleep/battery, outage and interrupted-write tests. No live HVAC claims.

Host/software follow-up:

- Validate actual HA Core MQTT entity schema/UI, local add-on Supervisor installation and aarch64 build/runtime. Broker integration and amd64 container are tested.
- Validate temperature range/capabilities per equipment; add bounded fan behavior only when confirmed. No schedules, presets, away or heat-cool support yet.
- Review complete proprietary outbound endpoints/listeners, historical Lua bot/debug shell/remote-support paths on exact firmware. Current hardening is deliberately partial.
- Add transactional commissioning journal/recovery; offline registry edits currently require backend shutdown/restart.
- Registry enrollment spans output and registry files without an all-or-nothing transaction; interruption produces a prepared but uninstalled credential. Inspect reports/files and explicitly revoke/retry; never assume success.
- Scope manager roles if multi-user use arises; current manager credential is full privilege. Add connection/rate limits if the service expands beyond isolated small-device use.
- Automatically scrub retained discovery for offline-revoked devices across bridge restarts; current manual broker cleanup documented.
- OS/container and legacy firmware CVE/SBOM analysis; pip-audit covers Python only. Verify binary/source correspondence and redistribution permissions before any release.
- Sign release manifests using an owner-controlled trust root when a real release exists; current manifests are unsigned integrity records.
