# Native entry-response fields and side effects

Read-only Ghidra review of the acquired client traced the registration field
callback at `0x976c0` and three called setters. Private exports, reference lists
and headless completion records remain under `private/native-entry-review-20261031`.
The existing project was opened read-only without reanalysis; no native code was
executed and no request was sent. The earlier
[protocol review](native-protocol-2026-10-30.md) remains the compatibility baseline.

The callback dispatches `platform_key` separately and logs its received value
before invoking the setter. The setter replaces a lock-protected, reference-counted
in-memory string and also logs the value on its copy-error path. This is another
potential disclosure path beyond the previously reviewed credential-header helper;
that helper's private logging candidate does not cover it. No actual key was
printed or used in this review. Whether commissioning requires this field remains
unverified; it should not be sent speculatively.

`tier_name` invokes a setter which can enumerate tier-dependent entries, call
native settings SetValue/Write and update in-memory state when the tier differs.
Consequently a nominal service-discovery reply can cause persistent native
settings work. Omitting the field and its operational effects must be evaluated
before treating any future entry exchange as observational. No such exchange or
settings write has been performed.

The callback handles update-version, update-URL, update-digest and critical-update
fields through a service-group bucket path. Other names containing `_url` reach a
generic URL setter. That setter recognizes exactly `upload_url`, `transport_url`,
`passphrase_url`, `ping_url`, `pro_info_url` and `weather_url`; an unknown URL name
is logged. The weather path can enqueue events. These paths do not establish
that every advertised service is necessary or that unknown fields are harmless.
No service was enabled and no update/control command was sent.

The URL setter measures the original input length, copies with a 256-byte snprintf
limit, then indexes the stack buffer using the original length to trim trailing
slashes. Independent LLVM disassembly corroborates this sequence and its original-
length indexed byte load/store loop. Oversized inputs therefore have a static
out-of-bounds concern; empty/all-slash edge cases also need review. This is not a
runtime exploit demonstration. A future minimal response codec must require short,
nonempty, explicitly allowed HTTPS URLs, avoid embedded secrets, and validate
before native delivery. Valid host JSON alone does not make these inputs safe.

The pinned NLE entry implementation supplies extra aliases and a tier value; that
is upstream behavior, not proof that Hearth should copy its whole response. No
production route/schema was added from these observations. Full entry completion,
trusted bootstrap, fetch/TLS/time setup, CAS/subscriptions, storage correction and
same-unit recovery still require independent validation.

## Host laboratory response correction

The existing experimental entry endpoint previously advertised empty weather and
update URLs. It now emits only its implemented transport URL. Its configured
origin uses the same private-IPv4/explicit-port HTTPS validator as offline
provisioning, which now also rejects controls, non-ASCII input and empty userinfo
before parsing/canonicalization. The resulting URL is bounded well below the
native copy limit. Regression checks require the exact minimal response and reject
unsafe origins; the route remains disabled in the normal runtime.

Omitting fields does not disable native cached/default service URLs, prove that
this minimal response completes registration, or close any network-isolation or
bootstrap gate. No entry reply has been sent to the actual unit. Host make check,
all 328 tests including TLS broker/container integration, and an explicit check of
the freshly rebuilt container passed. These are laboratory software results.
