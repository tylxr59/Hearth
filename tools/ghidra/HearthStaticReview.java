// Original Hearth static-review script. Never execute target firmware.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.nio.charset.StandardCharsets;

public class HearthStaticReview extends GhidraScript {
    private void save(Path path, String text) throws Exception {
        Files.writeString(path, text, StandardCharsets.UTF_8,
            StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        Files.setPosixFilePermissions(path, PosixFilePermissions.fromString("rw-------"));
    }
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2 || args.length > 17) throw new IllegalArgumentException("private output directory and function selectors required");
        Path requested = Paths.get(args[0]).toAbsolutePath().normalize();
        Path output = requested.toRealPath();
        if (!requested.equals(output) || !Files.isDirectory(output))
            throw new IllegalArgumentException("existing output without symlinks required");
        boolean privateOutput = false;
        for (Path ancestor = output; ancestor != null; ancestor = ancestor.getParent()) {
            if (ancestor.getFileName() != null && ancestor.getFileName().toString().equals("private") &&
                ancestor.getParent() != null && Files.exists(ancestor.getParent().resolve(".git"))) {
                privateOutput = true;
                break;
            }
        }
        var permissions = Files.getPosixFilePermissions(output);
        if (!privateOutput || !PosixFilePermissions.fromString("rwx------").containsAll(permissions))
            throw new IllegalArgumentException("owner-restricted output below repository private/ required");
        DecompInterface decompiler = new DecompInterface();
        int exported = 0;
        try {
            if (!decompiler.openProgram(currentProgram)) throw new IllegalStateException("decompiler initialization failed");
            for (int i = 1; i < args.length; i++) {
                Function function = null;
                if (args[i].startsWith("@")) {
                    var address = toAddr(Long.parseUnsignedLong(args[i].substring(1), 16));
                    function = getFunctionAt(address);
                    if (function == null) {
                        disassemble(address);
                        function = createFunction(address, "hearth_review_" + args[i].substring(1));
                    }
                } else {
                    var functions = currentProgram.getFunctionManager().getFunctions(true);
                    while (functions.hasNext()) {
                        Function candidate = functions.next();
                        if (!candidate.isExternal() && !candidate.isThunk() && candidate.getName().equals(args[i])) { function = candidate; break; }
                    }
                }
                if (function == null) { println("Requested function was not recovered."); continue; }
                StringBuilder references = new StringBuilder();
                ReferenceIterator iterator = currentProgram.getReferenceManager().getReferencesTo(function.getEntryPoint());
                int total = 0, calls = 0;
                while (iterator.hasNext()) {
                    Reference ref = iterator.next();
                    total++;
                    if (ref.getReferenceType().isCall()) calls++;
                    references.append(ref.getFromAddress()).append(" ").append(ref.getReferenceType()).append("\n");
                }
                String stem = function.getEntryPoint().toString() + "_" + function.getName().replaceAll("[^A-Za-z0-9_]", "_");
                save(output.resolve(stem + "_refs.txt"), "total=" + total + " calls=" + calls + "\n" + references);
                DecompileResults result = decompiler.decompileFunction(function, 30, monitor);
                if (result.decompileCompleted() && result.getDecompiledFunction() != null) {
                    save(output.resolve(stem + ".c"), result.getDecompiledFunction().getC());
                    exported++;
                }
            }
        } finally { decompiler.dispose(); }
        println("Static review complete; decompiled function count=" + exported);
    }
}
