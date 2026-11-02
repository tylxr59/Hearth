# Public distribution and installation

Status: implemented preview packaging, measured read-only acquisition, source-built
private kit and guided phases. A complete stock install/restore measurement and
portable USB setup remain unfinished.

Use one authoritative development repository. `backend/` is canonical, and
`tools.sync_integration` checks the generated self-contained HACS transport under
`custom_components/hearth/`. `tools.public_release` builds reproducible integration
and installer-source ZIPs with checksums. Matching0.x version tags trigger the
preview release workflow. HACS custom repository type is Integration; catalog
submission and a stable v1 release are separate later steps.

Fresh HA setup creates a unique local trust profile and device credential. Its
administrator-only commissioning endpoint exports public CA/CRL and the device
credential, never server/CA private keys or manager credentials. The USB CLI can
download this bundle with hidden token entry and no redirects, validate a unit
against it, and run a checked install/restore pair through independent RAM and
persistent-write prompts. No cloud account, firmware redistribution or arbitrary
downloaded executable is required.

Every writer image is bound to this owner's acquisition and commissioning bundle.
The public builder constructs two disjoint phases and their reverse-order restore
images. Its complete offline replay build and artifact reproduction do not establish
a fresh stock hardware installation. USB setup on other ports, configuration-
preserving uninstall and remaining recovery measurements must be completed before
a turnkey stock-device claim. Do not weaken the exact source/plan/custody binding.

HA code updates never silently reflash the thermostat. Proprietary native originals
come from each owner and remain private. See the current [installation guide](../installation.md)
and [firmware-kit guide](../development/firmware-kit.md).
