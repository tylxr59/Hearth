# Native startup, trust store and TLS review

This is offline static analysis of privately recovered Display-2.6 / 5.9.4-5
files. No target binary, listener query, lifecycle method or control command ran.
The thermostat stayed in native USB mode. Ghidra projects, decompiled C, library
hashes and the experimental modified copy remain private.

## Architecture consequence

Retain the provisional native cloud-protocol replacement route. The loopback
test-access code remains a candidate, but Ghidra found zero incoming references
to its identified initializer and thread entry. The known cleanup function had
one incoming call as a positive control. This supports dormant release code;
it does not prove that every possible indirect activation path is absent.
The earlier short-read framing concern remains unresolved. No production bridge
or test-access activation patch was implemented.

The cloud route also needs a concrete TLS correction: the native web-service
library installs a verification callback that overrides selected verification
failures. Replacing the CA file alone would not establish fail-closed time/CRL
validation. No deployment or installation path is enabled by this review.

## Configuration and trust-store evidence

The native client config is XML with `<a key=... value=...>` records. Reviewed
keys include `cloudregisterurl`, `rootcertpath`, `certblacklistpath` and
`rootunlockcertpath`. The recovered root config points at
`/nestlabs/share/certs/ca-bundle.pem`; a filesystem symlink resolves the certs
directory to `/etc/ssl/certs`. The extraction intentionally did not create that
symlink, so its JFFS2 metadata was reviewed separately rather than following a
firmware link onto the host.

That recovered bundle contains one self-issued Nest-named trust anchor. It does
not contain the affected eMudhra/emSign or AAA cross-signing trust families.
The [eMudhra incident](https://bugzilla.mozilla.org/show_bug.cgi?id=2083449)
therefore is not an evidenced bootstrap shortcut for this bundle: a forged chain
still needs an accepted trust anchor. Effective runtime config/alternate stores
were not measured; no compromised signing keys were obtained or used, and no
third-party domain was contacted through a forged certificate.

## Native callback behavior

Version markers identify OpenSSL 1.0.2h and libcurl 7.49.1. Public version-matched
references and hashes are in [native-tls-source-pins.json](native-tls-source-pins.json).
The reviewed fetch setup selects CAINFO, a CRL file and an SSL-context callback.
No explicit disable of peer/hostname verification was found in that setup.
The matched curl source defaults both checks on; this remains a source inference,
not a target handshake result or an audit of every networking path.

ARM disassembly, ELF relocations and Ghidra independently support this sequence:
`sslctxfun` registers SSL_VERIFY_PEER plus the native verification callback. When
preverification fails, the callback clears the context error and returns success
for these OpenSSL error numbers:

| Number | Meaning in OpenSSL 1.0.2h |
| --- | --- |
| 3 | Unable to get CRL |
| 9 | Certificate not yet valid |
| 11 | CRL not yet valid |
| 12 | CRL expired |

Certificate-expired error 10 is not in this override. This is not a claim that
all certificate validation or hostname checks are disabled. The
[OpenSSL callback contract](https://docs.openssl.org/1.0.2/man3/SSL_CTX_set_verify/)
explains why returning success continues verification; the
[matched error definitions](https://raw.githubusercontent.com/openssl/openssl/OpenSSL_1_0_2h/crypto/x509/x509_vfy.h)
identify the specific cases above.

## Private offline remediation candidate

A separate private, non-executable review copy replaces one ARM instruction in
the reviewed SSL-context hook: the callback-pointer load becomes a NULL pointer
assignment. The context and SSL_VERIFY_PEER arguments remain unchanged. LLVM
disassembly and a fresh Ghidra import show a call equivalent to
`SSL_CTX_set_verify(context, SSL_VERIFY_PEER, NULL)`. Original library bytes were
preserved and comparisons confirmed no changes outside that instruction word.
The private review record retains exact input/output hashes and offsets.

Per OpenSSL's documented API, a NULL callback uses the default preverification
result. This is the intended fail-closed correction, not a target-tested TLS fix.
No modified library or proprietary bytes are shipped in Git. No file was
installed on the thermostat. The candidate still requires exact-profile review,
trusted clock bootstrap, an owner CA and fresh CRL, wrong-CA/hostname/time tests,
transactional commissioning and the existing backup/restoration gates. None of
those gates is waived by a four-byte offline change.

## Ghidra tooling and validation

The installed Ghidra 12.1.2 DEV ran headless with installed Java 27; default Java
17 was left unchanged. Native-client analysis completed without a timeout and
exported seven reviewed functions. TLS analysis exported the original callback
and hook; the modified-copy import exported the hook with its NULL argument.
These are static decompilation observations, not execution/emulation of firmware.

[HearthStaticReview.java](../../tools/ghidra/HearthStaticReview.java) is original
reusable scripting code. Its final integration run exported two TLS functions
to owner-only private storage. A deliberate public output path was rejected and
created zero files. Program imports, Java user data, logs and exports remained
private throughout. Headless logs can contain firmware hashes and must not be
published. See the [usage instructions](../../tools/ghidra/README.md).

Next: review credential/bootstrap persistence and the native transport contract;
prepare an isolated target-validation plan only after restoration/commissioning
gates are satisfied. No live validation occurred in this milestone.
