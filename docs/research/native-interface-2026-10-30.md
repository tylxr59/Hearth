# Native local-interface static review

Inputs are the owner's privately reconstructed Display-2.6 / 5.9.4-5 root0
`nlclient`, `osm`, libraries and startup policies. Their hashes and complete
symbols/strings/disassembly stay private under `private/native-interface-20261030`.
Only static ELF/data inspection occurred. No native binary, D-Bus method, socket
connection or control command was executed; no thermostat mode change was needed.

## D-Bus: traced registrations concern other services

Three direct nlclient interface-registration calls were traced from ARM code into
their null-terminated name/method/handler tables. They contain ten methods:

- Four network-sniffer methods, including packet inspection, gateway-change and
  Wi-Fi-reset handling.
- Five SCPM sleep/shutdown lifecycle methods.
- One heartbeat request method.

The installed nlclient policy permits root ownership/sending and denies default
send access. None of the traced methods is a thermostat setter. This is evidence
about those specific registrations, not proof that all possible IPC is absent.
SCPM/sniffer/lifecycle methods must not be invoked as diagnostic control probes.

## Loopback test-access candidate

Native code contains a TCP server that passes port 1234 and IPv4 127.0.0.1 to
NSPR bind/listen operations. Its dispatcher searches a fixed 104-entry command
table. Reviewed entries include `currenttemp`, `humidity`, `targettemp`,
`targettemprange`, `temperaturescale`, `off` and `version`. Other entries perform
resets, simulated inputs and power-related operations; a generic command forwarder
would violate Hearth's boundary and is not implemented.

The `targettemp` handler distinguishes a no-argument query from a one-value setter,
has a native-mode guard, and calls application virtual methods for setting and
reading the target. It multiplies/divides by 65536 around native integer storage.
The current-temperature query uses the same factor. The mode-name array names
HEAT, COOL, RANGE, MIXED, EMERGENCY, HUMIDIFY, DEHUMIDIFY and HOTWATER; the single
target handler admits indices 0, 1 and 4. This does not establish the unit's HVAC
capabilities, runtime wire units, input limits, persistence or actuation safety.
The table's command names differ from some legacy usage-message names; future
code must use the reviewed dispatch names, not copy help text as a wire contract.

Two material unknowns prevent promoting this to a production bridge:

1. Startup/enablement is unproven. No direct initialization/thread-start reference
   to the identified test-access entry points was found in the current pass.
   The installed client config/monit entry has no testaccess setting. Present code
   and cleanup paths do not prove an active listener; it may be dormant build code.
2. The receive loop accumulates 2047-byte reads and dispatches after a short read,
   then writes a response and closes. TCP short reads are not request boundaries.
   Fragmentation could dispatch an incomplete setter argument. No runtime framing
   tests or robustness fix has been established. Merely making one client send()
   call would not prove this safe.

The setter path preserves an application entry point in static code, but its
native event handling and effects remain unverified. No live probe was attempted.
Weave-related symbols also exist; compiled Weave device-manager/client code does
not establish an authenticated thermostat-control server or pairing capability.

## Reproducible offline tooling and decision

`python -m tools.elf_review PRIVATE_ELF --table ADDRESS --commands ADDRESS COUNT
--output PRIVATE_JSON` parses bounded ARM ELF32 file mappings and reviewed table
addresses. It checks identifiers, executable handler mappings, terminators,
counts and duplicate names; rejects holes, BSS-only addresses and ambiguous
mappings. It writes only a fresh owner-restricted private report. Public stdout
contains table/method counts, not strings, binary hashes or commands. It cannot
connect to or execute firmware. Addresses are supplied from manual disassembly
review; this is not automatic interface discovery or runtime introspection.

The actual private report contains three bus tables/ten methods and 104 test-access
commands. Twenty synthetic tests cover malformed ELF/address/table bounds and
private output behavior. The actual binary scan also completed successfully.

Retain the provisional host transport architecture. Treat test-access as a
specific native bridge candidate for later enablement/framing review, beginning
with separately reviewed read-only queries if a reachable listener is evidenced.
Do not expose setters, raw commands or a production native adapter yet. Actual
credential/TLS/native transport inspection can now proceed from recovered files.
