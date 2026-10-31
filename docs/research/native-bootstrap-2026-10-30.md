# Native credential and registration review

Offline static analysis of the privately recovered Display-2.6 / 5.9.4-5
client. No firmware was executed, installed or sent to the thermostat. No
additional USB restart was needed. Original binaries, settings and captures
remain unchanged; decompilations, binary hashes and the modified review copy
remain private.

## Credential lifecycle

ARM disassembly and Ghidra support the following behavior in the reviewed path:

1. With authentication enabled, initialization first tries the settings keys
   `assigned_cred_id` and `assigned_cred_secret`. Both reads must succeed before
   they are copied into the active credential strings.
2. If assigned settings are unavailable, the client selects default credentials.
   The fallback consults the environment's default-identifier/default-secret
   keys, with compiled fallback strings when those values are absent or empty.
   Those strings are not enrolled Hearth credentials and are not reproduced here.
3. Registration and reviewed transport fetches pass the active identifier and
   secret to `nlEventFetchURL::EnableBasicAuth`. The getters use the same active
   string offsets populated by the settings and fallback paths. This is static
   evidence, not an observed authenticated target request.
4. `X-nl-set-client-credentials` is a **response** header. Its value is copied
   through a 1024-byte buffer and split at the first ASCII space into an
   identifier and secret. Separate setters update active strings and call
   `nlSettings::SetValue` for the assigned settings. No length/entropy policy or
   transactional two-key commit was established by this path. A storage call is
   not proof of durable persistence or successful restoration after interruption.
5. The helper is called by generic fetch completion and subscription header/body
   handling. Generic completion processes the header before its HTTP-status
   dispatch; credential delivery is not confined to successful registration.
   The header lookup uses a case-insensitive substring search, requires `: `
   and a terminating CRLF, and does not establish a header-name start boundary.
   Avoid duplicate/ambiguous headers; an ordinary host HTTP parser is not a
   faithful model of this native parsing behavior.
6. A 401 while using assigned credentials selects the default credential path.
   Thus revocation must continue rejecting fallback requests; a claimed device
   ID or default credential must never silently restore enrollment.

The setters also mark the active credentials as assigned. Their storage calls
are separate and their return values do not establish a successful atomic pair
update. Settings-file ownership, serialization, flush behavior, restart readback,
power-loss rollback and native log retention remain to be traced/validated.

## Credential disclosure and private remediation candidate

When either credential changes, the reviewed helper passes both the new ID and
secret to a component log call at level 4. This is distinct from the settings
serialization path, which recognizes the secret key for special handling.
Suppressing debug fetch output alone does not remove this call. Whether this
message reaches persistent storage or uploads depends on runtime logging paths
that have not been measured.

A separate owner-only, non-executable review copy replaces the conditional branch
into that logging block with one ARM no-op. Both credential setters still run;
execution continues into the existing suspend-time header processing. Input
instruction/context checks and whole-file comparison restrict the change to
one four-byte instruction span. Original client bytes were preserved.

LLVM disassembly and a fresh Ghidra import independently checked the candidate:
the changed helper retains both setter calls and suspend-time handling, while
the changed-credential logging call is absent from its decompiled control flow.
This is a narrowly reviewed candidate, **not** a complete credential-log audit,
runtime-tested fix or deployable firmware. No proprietary patch bytes, modified
binary or binary hash are included in Git. Existing backup/restoration and
commissioning gates still apply before any installation.

## Registration and transport observations

The registration builder selects `application/x-www-form-urlencoded` and the
fetch method value used for POST. Its base fields are `reset`, `mac`, `model`,
`request_id` and `software_version`; branches add `wireless_reg_domain` and
`backplate_model`. It advertises `X-nl-accepts: register-redirection`. With native
authentication disabled, it uses a device-ID header instead of Basic auth;
that branch is not an acceptable Hearth authentication design.

The client recognizes a `transport_url` result and has a JSON POST builder for
`/v7/put`, plus a retrieval builder for `/v7/device/<bucket-key>`. Reviewed request
headers include protocol version 1 and device software version. These corroborate
parts of the pinned NLE protocol research; they do not establish a working entry
response, complete pairing flow or a correct revision/CAS/subscription adapter.
The bucket parser has distinct revision and timestamp handling. Its existence
does not justify discarding those fields in a production decoder.

## Hearth consequence and checks

Keep the normal runtime's native routes disabled. Do not add serial-derived
secrets, accept stock defaults, or interpret `d.<claimed-id>.<suffix>` as an
enrolled identity. The canonical API's explicit manager enrollment and unique
credential checks remain the laboratory authentication contract. A future native
commissioner needs an owner-controlled initial secret, verified TLS, an explicit
identifier binding, bounded rotation/acknowledgment, private rollback material
and a persistence readback test. Header delivery alone supplies none of those.

Three new host regression tests check that native-looking identity/fallback
claims cannot enroll or restore a revoked device, an inbound credential header
cannot rotate/echo a secret, and normal runtime still has no registration route.
These use synthetic claims and randomly generated laboratory secrets; no native
default secret or real device identifier is present in the fixtures.

Ghidra exported 25 original functions across three bounded review runs and one
function from the separate candidate. Completion markers and output counts were
checked; exports were not treated as successful based on launcher status alone.
`make check` passed and the host suite passed 174 tests with two optional
broker/container tests skipped. Earlier full integration evidence remains in
its dated report; it was not repeated for these test/documentation-only changes.

Next: trace settings serialization/commit and credential-related log/upload paths,
then finish the entry response and revision/subscription state-machine mapping.
Any later target validation also requires the unresolved recovery gates. No
native compatibility, credential installation, TLS handshake or HVAC operation
was demonstrated here.
