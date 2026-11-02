# Develop Hearth

Read [status](development/status.md), [roadmap](development/roadmap.md) and the
root contributor instructions. User-facing installation and controls are documented
separately; dated experiments are retained under development history/research.

```sh
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-dev.lock
make test
make check
.venv/bin/python -m tools.sync_integration --check
.venv/bin/python -m tools.check_native_ha build/ha-check --engine podman
```

`backend/` is canonical. Generate the self-contained HACS runtime with
`python -m tools.sync_integration`; never hand-edit `_backend/`. The package tool
copies only fixed public runtime files, not profiles or owner firmware.

Build public preview artifacts with `python -m tools.public_release build/preview`.
A matching0.x tag publishes the integration ZIP, installer-source ZIP and checksums.
No build command activates HA, changes the thermostat or runs a physical control.

The [firmware-kit guide](development/firmware-kit.md) distinguishes the implemented
writer frontend from the unfinished turnkey stock-device pipeline. Do not remove
source/plan/backup checks in pursuit of easier distribution.

Pinned protocol references live in [upstreams](research/upstreams.json).
New code derives from protocol behavior; it is not copied reference source.
Synthetic coverage, actual device results and equipment results must remain
separate in release claims. Update the compatibility matrix when evidence changes.
