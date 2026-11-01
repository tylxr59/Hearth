# Public distribution and installation proposal

Status: proposed; no new repository, public release, HACS submission or public
installer has been created. Finish native controls and equipment validation first.

Keep one authoritative development source. Produce versioned, reproducible HA
integration artifacts in CI, with a declared transport/installer compatibility
version. HACS installation needs a self-contained integration; our current nested
source and generated private-development packaging are not directly a public
HACS repository. Adapt layout/release packaging deliberately. If a dedicated
HA distribution repository is useful later, generate its contents from the same
reviewed source rather than maintain manual copies.

Publish a GitHub release with its integration ZIP, changelog, compatibility matrix,
source/license/provenance and appropriate artifact verification. Early adopters
can use a custom repository. Default HACS catalog inclusion is a separate later
submission after HACS Action/Hassfest and release requirements pass. HACS installs
integration files; it does not install thermostat modifications.

Proposed onboarding:

1. Install the HA integration and use its setup wizard to select the thermostat-
   reachable local address, prepare local TLS/trust and per-device credentials,
   and produce a one-use commissioning bundle. Ordinary users should not need
   root SSH access to HA or to manually copy certificate/profile files.
2. Run a guided desktop USB installer, initially on the actually supported host
   platforms. Pair it to that commissioning bundle, confirm the local endpoint,
   identify model/firmware/active partition, preserve fresh private originals and
   inspect the exact supported operation. Refuse unsupported devices/versions.
3. Guide the manual ROM entry and show the actual modification/recovery limits
   before persistent work. Verify complete originals, native-compatible encoding,
   backups, sufficient resources and exact readback. Preserve an independent
   restore package and logs that omit credentials/identifiers by default.
4. Reconnect normal WiFi, verify HA registration and reported telemetry, then
   perform supervised control validation before any equipment commissioning.

A Python CLI with prompts is a reasonable first frontend; the verified operation
engine should remain separate so a desktop UI can reuse it. A command such as
`hearth setup` is a proposed user experience, not an existing supported command.

The present research path still uses per-unit private compile-time plan/receipt
bindings and developer build containers. A public installer must address that
explicitly: either reproducible per-unit preparation or a separately reviewed
public RAM bootstrap accepting a strictly bounded per-session plan. Shipping
opaque owner firmware or silently removing custody/region guards is not a shortcut.
Distribute original public helper/bootstrap code and supported source components;
acquire proprietary native originals only from each owner's device.

Integration updates should update HA code without silently reflashing a thermostat.
Device updates require explicit compatible plans and recovery handling. HA setup
addresses and credentials must never be published as defaults in release artifacts.

References: [HACS integration layout](https://www.hacs.xyz/docs/publish/integration/),
[release manifests](https://hacs.xyz/docs/publish/start/), and
[default-catalog requirements](https://hacs.xyz/docs/publish/include/).
