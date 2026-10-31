# Local laboratory setup

Use a current Linux host. No upstream installer or ARM binary is needed. Runtime Python dependencies are exactly pinned in pyproject and, including transitives and SHA-256s, requirements.lock. Use requirements-dev.lock for tests/scans. Build files do not auto-run scans online during service startup.

## TLS and simulator

After README's registry preparation:

```sh
umask 077
mkdir -p private/tls
openssl req -x509 -newkey rsa:3072 -nodes -days 7 \
  -subj '/CN=hearth-lab' -addext 'subjectAltName=IP:127.0.0.1' \
  -keyout private/tls/server.key -out private/tls/server.pem
.venv/bin/python -m backend.api --registry private/registry.json \
  --cert private/tls/server.pem --key private/tls/server.key
```

In another terminal:

```sh
.venv/bin/python -m tools.simulator --device-file private/device/device.json \
  --ca private/tls/server.pem --steps 120
```

A self-signed certificate is only trusted explicitly in this lab. Real client trust/pinning and time behavior are unresolved. Generate a proper private local CA and SAN matching the chosen IP for a permanent host. No disabled certificate checking is supported. Plain HTTP binds are permitted only for explicit loopback developer use; never proxy that mode onto an untrusted network.

Read status and issue a simulated command without printing or putting the manager credential in shell command arguments:

```python
import json, ssl, urllib.request
admin = json.load(open('private/admin.json'))['token']
context = ssl.create_default_context(cafile='private/tls/server.pem')
url = 'https://127.0.0.1:8443/v1/manage/devices/02AA01AB501203EQ/commands'
request = urllib.request.Request(url, data=json.dumps({
    'operation': 'temperature', 'value': 22.5}).encode(), headers={
    'Authorization': 'Bearer ' + admin, 'Content-Type': 'application/json'})
with urllib.request.urlopen(request, context=context) as response:
    print(response.status)  # No credentials in the command response.
```

Management enrollment/rotation POST/PUT accepts only `{"capabilities":{"modes":["off","heat"],"fan":false}}`. The server uses OS randomness and returns the new credential once over the authenticated TLS connection with no-store caching. Save it directly to a 0600 file, never ordinary logs; actual device installation is not implemented. DELETE revokes immediately. Offline CLI prepare/--rotate/revoke requires stopping the backend first and restarting it afterward. Keep old private config until a rollback is possible, but revocation intentionally invalidates the old credential.

Revocation also stores the validated identity in the registry's optional `revoked`
list. On its next MQTT connection, the bridge retains offline availability and
deletes that identity's retained discovery/state, including after an offline CLI
revocation and backend restart. Queue failures retry on a later publish tick;
the list survives successful cleanup and is replayed after reconnect. Explicit
re-enrollment removes the identity from this list, and active identities are
always excluded from deletion. This list contains identifiers only, without old
credentials, capability data or telemetry.

Older registries remain readable without the optional field. An identity already
forgotten by an older release cannot be reconstructed automatically: with the
backend stopped, explicitly revoke that known identity once and restart, or use
an authorized broker admin tool. Keep the bridge running until broker/HA cleanup
is observed before uninstalling. Correct broker ACLs and connectivity are needed;
a local publish-queue acceptance is not proof of successful broker deletion.

To rotate the manager credential, stop the backend, run `python -m provisioning.cli rotate-admin --registry private/registry.json --output private/admin-new.json`, then restart and use the new private file. Existing output is never overwritten; the old manager credential becomes invalid after restart. Device credentials do not change.

## MQTT

Create a dedicated local broker account using its secure admin tooling. See homeassistant/mosquitto.acl. Both broker and HA should use authenticated TLS. Create private/mqtt.json mode 0600:

```json
{"host":"mqtt.lan","port":8883,"username":"hearth-bridge",
 "password":"REPLACE_WITH_UNIQUE_BROKER_PASSWORD","ca":"/absolute/path/to/local-ca.pem"}
```

Add `--mqtt-config private/mqtt.json` to the backend invocation. Broker certificate hostname must match. The backend speaks MQTT v5, with no persistent session and no retained commands. The normal HA MQTT integration discovers climate entities; do not enable optimistic mode or retain HA commands. Discovery includes current humidity only when telemetry exists; no actual Nest fan capability is asserted by this prototype.

## Firmware artifacts

`make demo` creates only synthetic inputs. For a user-owned unpacked root, prepare a reviewed JSON object mapping the four paths in firmware.prepare.FILES to their SHA-256 digests. Do not take a hash from a newly downloaded file as proof of trust. Keep root dumps and modified private files out of Git.

```sh
.venv/bin/python -m firmware.prepare --root private/unpacked-root \
  --input-manifest private/root-hashes.json --endpoint https://192.168.50.2:8443 \
  --output build/review.tar
.venv/bin/python -m firmware.harden --root private/unpacked-root \
  --input-manifest private/root-hashes.json --endpoint https://192.168.50.2:8443 \
  --output private/offline-replacements
```

The first command emits a deterministic archive of declarative edits, blockers and SHA256SUMS, containing no proprietary config or credentials. The second emits private replacement config/init/shadow files and an explicit removal list for local review. It locks the root password and removes recognized NLE/rootme/Dropbear/sshconnect rcS lines. Ambiguous shell constructs cause failure. It does not remove files from the source, replace trust stores, install credentials, rewrite all boot paths, make a bootable image or enforce runtime security. Preserve CA stores, unknown services, hardware and power-management configuration. Wildcard Monit includes still require actual removal of the HTTP service file listed in the review manifest.

## Builds and scans

`make wheel` installs the separately hash-locked build backend and builds a Python wheel. `make image` builds an unprivileged backend image from a pinned multi-architecture Python base digest and hash-locked packages. `make addon` assembles a local add-on directory. `make release` creates a deterministic source tar, per-file provenance manifest and SHA256SUMS; no publishing or signing occurs. Re-running into existing output directories refuses overwrite. Remove only generated output you deliberately intend to regenerate.

Source and inert tar content is reproducible for identical input; Docker image identity is not claimed byte-reproducible (builder metadata, pip bytecode/install metadata and base build history can vary). Python, kernel and container OS security require ongoing patch review. `make audit` checks both runtime and build dependencies against advisory services and therefore needs internet during development; runtime needs none. A clean scan is not a proof of firmware or HVAC safety.

Rootless Podman is also supported for the host laboratory:

```sh
make image CONTAINER_ENGINE=podman
HEARTH_CONTAINER_ENGINE=podman HEARTH_BROKER_TEST=1 HEARTH_CONTAINER_TEST=1 .venv/bin/pytest -q
```

Tests preserve the invoking UID for private fixture bind mounts under rootless
Podman. They still verify the backend image's default UID 10001 separately.
These are simulated loopback services; they do not access the thermostat.

Read-only intake now recognizes normal Nest USB `2464:0002` as well as TI
candidates. Neither detection nor ROM enumeration verifies a generation or
payload compatibility. Watch changed sysfs snapshots with:

```sh
.venv/bin/python -m provisioning.cli detect --watch 60
```

To share a diagnostic plist, pipe its bytes to
`.venv/bin/python -m provisioning.cli inspect-info`. The tool emits only
allowlisted model/version/partition/update fields, never serial, MAC or network
sections. It reads at most 16 KiB, rejects malformed/ambiguous XML and does not
mount or write a device. Reading the USB volume itself still needs separately
authorized access and a freshly verified device path.

The separate [experimental RAM probe](../firmware/probe/README.md) builds a minimal
diagnostic kernel, not a thermostat firmware or acquisition/recovery image.
Its device execution is pending; its explicit execution command is never called
by normal build, test, artifact or runtime targets.
