# Experimental native storage correction

Original ARM compatibility code for the privately reviewed Display-2.6 / 5.9.4-5
library. **Uninstalled and not yet target-validated.** This is not an installer,
HVAC controller, replacement firmware or recovery procedure. Use only in the
separate [synthetic RAM comparison](../settings_compat_probe/README.md).

The implementation keeps the original native writer and serialization:

- A per-call, thread-local context identifies its temporary-file descriptor.
  Any short/failed entry write stays sticky and makes the existing file-sync
  failure path reject replacement. Unrelated descriptors are forwarded normally.
- Failed native commits restore the dirty flag under the object's original lock.
  No concurrent setter value or dirty flag is cleared by this correction.
- The native string setter still performs its original locking and callback.
  Aliased old-string arguments stay live through that callback and are released
  afterward. The bounded deferred list fails before mutation if exhausted.
- The configuration entry operation allocates/copies before changing the table,
  checks hash insertion and releases the old value only after success. Native
  key/value ownership and pointer comparison were separately reviewed. Empty
  existing entries and inputs aliasing old strings are handled without leaks.
  A runtime allocator/comparator guard delegates unrecognized table contracts to
  the original operation, preserving unknown configuration implementations.
- Value-bearing component logs within a writer call are suppressed on that thread.
  Failures emit a static status-only notice. The allocation replacement emits no
  key/value error messages. An ARM assembly tail stub forwards unrelated variadic
  logs with their original registers, stack and return address.

The object adapter has compile-time ARM32 checks and a separately required private
ABI review. It uses the reviewed field offsets and native allocation/locking APIs;
it does not alter calibration, services, controls or binary bytes. Startup symbol
binding fails if required symbols are unavailable. This is startup-only preload
experimentation, not a supported late-injection or production fallback mechanism.

Host checks use original fixtures and the installed **host** NSPR under ASan/UBSan.
They cover file replacement blocking, retry, unrelated descriptors, nested and
concurrent writers, allocation/hash failure, ownership, input aliases and callback
lifetimes. No recovered firmware is linked or executed on the host. Clang/LLD
compile only original code with generated ABI stubs; those stubs are never packed.
Public hash API/ownership references are [pinned](sources.json), not vendored.
The actual native callbacks/comparator were inspected independently; no
source/binary-correspondence claim is made from an upstream API reference.

Remaining gates include native target comparison, application startup/integration,
other credential log paths, actual permissions, two-key credential transactions,
serialized-value limits, trusted TLS/time configuration, same-unit restoration and
physical bench validation. This correction alone cannot establish secure
commissioning or legacy-library safety. Keep all installed/native originals intact.
