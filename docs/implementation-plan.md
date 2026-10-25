# Iteration plan and completion evidence

1. Inspect references, local audit availability, source and binary provenance. Completed source inspection; workspace initially contained LICENSE and Git metadata, no audit or firmware. Historical root/config/kernel source and NLE prebuilt headers inspected statically. No firmware executable run.
2. Choose smallest defensible boundary. ADR-0001 retains native control, defers on-device bridge pending local API evidence, implements authenticated host transport laboratory.
3. Build backend and simulation. Implemented canonical API, partial Nest PUT decoder, state/intent separation, command bounds, separate credentials, persistence of credential hashes only. Complete Nest pairing and long-poll transport remain blocked by evidence gaps.
4. Build Linux preparation and firmware tooling. Implemented unique credentials, reports, read-only USB enumeration, input pin checks, deterministic inert review bundles and offline replacement generation. No flashable image, credential installation, generation verification, automatic backup or device apply support.
5. Integrate Home Assistant. MQTT climate discovery, mode/temperature/action/humidity/fan/availability/device info; real TLS broker test and add-on container build. HA Core/Supervisor runtime and device capabilities not validated.
6. Validate. Regression tests, property tests, Ruff, Bandit, pip-audit, reproducibility checks, unprivileged container smoke test. Results in security report.
7. Prepare hardware work. Explicit authorization and isolated bench required; repeatable capture, backup, TLS/authentication, native regulation and failure matrix in hardware plan. No hardware claims.

Deliverable boundaries are intentional: a guessed D-Bus setter or a permissive cloud emulator would create misleading compatibility and physical risks. Continue with read-only firmware acquisition and authenticated protocol capture before enabling deployment. The prototype currently provides the host-side foundation and inspectable modifications, not a finished Valetudo-equivalent firmware.
