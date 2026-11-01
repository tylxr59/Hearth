// Original Hearth static-review helper. No target code execution or file patching.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.program.model.listing.Function;
import ghidra.program.model.address.Address;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashSet;

public class HearthURLReview extends GhidraScript {
    private void save(Path output, String name, String text) throws Exception {
        Path path=output.resolve(name);
        Files.createFile(path,PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------")));
        Files.writeString(path,text,StandardCharsets.UTF_8,StandardOpenOption.WRITE);
    }
    public void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length<1||args.length>9) throw new IllegalArgumentException("private output and up to eight reviewed global selectors required");
        Path requested=Paths.get(args[0]).toAbsolutePath().normalize(), output=requested.toRealPath();
        boolean allowed=false;
        for(Path p=output;p!=null;p=p.getParent()) {
            if(p.getFileName()!=null&&p.getFileName().toString().equals("private")&&p.getParent()!=null&&Files.exists(p.getParent().resolve(".git"))) allowed=true;
        }
        if(!allowed||!requested.equals(output)||!PosixFilePermissions.fromString("rwx------").containsAll(Files.getPosixFilePermissions(output)))
            throw new IllegalArgumentException("owner-only repository private output required");
        byte[] needle=("http://clients3.google.com/generate_204"+'\0').getBytes(StandardCharsets.US_ASCII);
        Address address=currentProgram.getMemory().findBytes(currentProgram.getMinAddress(),needle,null,true,monitor);
        if(address==null||currentProgram.getMemory().findBytes(address.add(1),needle,null,true,monitor)!=null)
            throw new IllegalStateException("one exact terminated probe URL required");
        StringBuilder references=new StringBuilder();
        LinkedHashSet<Function> selected=new LinkedHashSet<>();
        var iterator=currentProgram.getReferenceManager().getReferencesTo(address);
        while(iterator.hasNext()) {
            var ref=iterator.next();
            Function f=getFunctionContaining(ref.getFromAddress());
            references.append(ref.getFromAddress()).append(" ").append(ref.getReferenceType()).append(" ").append(f==null?"no-function":f.getName()).append("\n");
            if(f!=null) selected.add(f);
        }
        // Follow reviewed initialized string objects without dumping their data.
        for(int i=1;i<args.length;i++) {
            Address base=toAddr(Long.parseUnsignedLong(args[i],16));
            for(int offset=0;offset<32;offset+=4) {
                var refs=currentProgram.getReferenceManager().getReferencesTo(base.add(offset));
                while(refs.hasNext()) {
                    var ref=refs.next();Function f=getFunctionContaining(ref.getFromAddress());
                    references.append("global ").append(ref.getFromAddress()).append(" ").append(f==null?"no-function":f.getName()).append("\n");
                    if(f!=null&&selected.size()<16) selected.add(f);
                }
            }
        }
        save(output,"url-references.txt",references.toString());
        LinkedHashSet<Function> direct=new LinkedHashSet<>(selected);
        for(Function f:direct) {
            for(Function caller:f.getCallingFunctions(monitor)) if(!caller.isExternal()&&selected.size()<16) selected.add(caller);
        }
        DecompInterface decompiler=new DecompInterface();int count=0;
        try {
            if(!decompiler.openProgram(currentProgram)) throw new IllegalStateException("decompiler failed");
            for(Function f:selected) {
                var result=decompiler.decompileFunction(f,30,monitor);
                if(result.decompileCompleted()&&result.getDecompiledFunction()!=null) {
                    String label=f.getEntryPoint().toString()+"_"+f.getName().replaceAll("[^A-Za-z0-9_]","_");
                    save(output,label+".c",result.getDecompiledFunction().getC());count++;
                }
            }
        } finally { decompiler.dispose(); }
        println("Bounded private URL static review complete; exported functions="+count);
    }
}
