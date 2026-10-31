# Private headless static review

`HearthStaticReview.java` exports selected decompilations and incoming-reference
reports from an imported ARM program. It never executes target firmware. It may
create function labels in the private Ghidra database; original ELF bytes are
unchanged. No emulator, debugger, target connection or cloud service is used.

The output directory must already exist beneath this checkout's ignored
`private/`, have no symlinks, and allow owner access only. Exports use fresh
filenames and mode 0600. Function selectors are exact non-external function
names or `@HEX_ADDRESS`; at most 16 selectors and 30 seconds per decompilation
are allowed. Missing functions are reported without dumping target data.
This is static research tooling, not a target introspection/control API.

Keep projects, Java user data, logs and exports private. Ghidra's own logs can
include binary hashes, so redirect them before invoking the launcher. On this
PC Ghidra 12.1.2 DEV requires JDK >=21; Java 27 is installed alongside the
default Java 17. No JDK/system setting was changed.

Example after creating owner-only private directories:

```sh
umask 077
JAVA_HOME=PATH_TO_INSTALLED_SUPPORTED_JDK \
GHIDRA_HEADLESS_JAVA_OPTIONS='-Duser.home=ABSOLUTE_PRIVATE_JAVA_HOME' \
  PATH_TO_GHIDRA/support/analyzeHeadless ABSOLUTE_PRIVATE_PROJECTS PROJECT_NAME \
  -import ABSOLUTE_PRIVATE_ELF -analysisTimeoutPerFile 300 -max-cpu 4 \
  -scriptPath ABSOLUTE_REPOSITORY/tools/ghidra \
  -postScript HearthStaticReview.java ABSOLUTE_PRIVATE_OUTPUT FUNCTION_NAME \
  > ABSOLUTE_PRIVATE_LOG 2>&1
```

For an existing project, use `-process PROGRAM_NAME -noanalysis -readOnly` in
place of `-import`. Use fresh output directories/files for each run. Program
virtual addresses may differ from raw ELF addresses when Ghidra relocates a
shared object; prefer reviewed function names in that case.

Actual integration checks exported the two TLS functions into private storage.
A deliberate output outside `private/` was refused and created no exports.
The original research script also reviewed seven client functions, recovering
the known cleanup call as a positive control while finding no incoming
initializer/thread-entry references. Those observations are static evidence,
not proof of runtime reachability or absence of indirect calls.

For automated use, verify the fixed completion message and expected fresh exports
in the private log/output. The headless launcher can return zero even when a
post-script throws; launcher exit status alone is not a successful review.
