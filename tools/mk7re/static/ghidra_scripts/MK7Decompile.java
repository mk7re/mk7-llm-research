// Decompiles the functions containing the given addresses and writes one C file
// per function into the output directory: <outDir>/<entry>.c
// Usage (headless): -postScript MK7Decompile.java <outDir> <hexAddr>...
//@category MK7

import java.io.File;
import java.io.PrintWriter;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

public class MK7Decompile extends GhidraScript {

	@Override
	public void run() throws Exception {
		String[] args = getScriptArgs();
		if (args.length < 2) {
			throw new IllegalArgumentException("usage: MK7Decompile <outDir> <hexAddr>...");
		}
		File outDir = new File(args[0]);
		outDir.mkdirs();
		DecompInterface decompiler = new DecompInterface();
		decompiler.openProgram(currentProgram);
		try {
			for (int i = 1; i < args.length; i++) {
				Address addr = toAddr(Long.parseLong(args[i], 16));
				File out = new File(outDir, String.format("%08x.c", addr.getOffset()));
				try (PrintWriter writer = new PrintWriter(out, "UTF-8")) {
					Function f = getFunctionContaining(addr);
					if (f == null) {
						disassemble(addr);
						f = createFunction(addr, null);
					}
					if (f == null) {
						writer.println("// no function at " + addr);
						continue;
					}
					DecompileResults res = decompiler.decompileFunction(f, 120, monitor);
					writer.println("// " + f.getName(true) + " @ " + f.getEntryPoint() +
						"  (" + currentProgram.getName() + ")");
					if (res.decompileCompleted()) {
						writer.print(res.getDecompiledFunction().getC());
					}
					else {
						writer.println("// decompilation failed: " + res.getErrorMessage());
					}
				}
			}
		}
		finally {
			decompiler.dispose();
		}
	}
}
