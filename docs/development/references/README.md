# Pinned references

Machine-readable pins and audits that the code and the history rely on.

| File | Purpose |
| --- | --- |
| `upstreams.json` | Pinned upstream repositories (NLE, NestDFUAttack, loaders…) with file hashes. Read by `python -m tools.fetch_research` |
| `native-tls-source-pins.json`, `connman-5.9.4.json`, `glibc-relocation-2.19.json`, `bchlib-2.1.3.json` | Public source pins behind specific reviews (TLS, ConnMan, glibc ABI, BCH) |
| `binary-inventory.json` | Hashes and sizes of inspected upstream prebuilt binaries (provenance unverified) |
| `filesystem-snapshot-source-2026-10-31.json`, `nand-raw-write-source-2026-10-31.json` | Source pins for historical snapshot and raw-write experiments |
| `python-dependencies.json`, `*-dependency-audit.json` | Dependency inventories and pip-audit results |

The BCH pin the NAND verifier actually uses lives next to it, in
`tools/nand_archive/bch-input.json`.
