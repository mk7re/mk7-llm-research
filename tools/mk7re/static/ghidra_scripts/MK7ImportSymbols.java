// Prepares a raw MK7 code.bin for analysis: splits the single block the binary
// loader creates into .text/.data, adds .bss, and applies a symbol map written
// by `mk7 ghidra` (addr <TAB> ns1 <US> ns2 <US> leaf <TAB> full signature).
// Safe to re-run on an existing program to refresh names.
//@category MK7

import java.io.BufferedReader;
import java.io.FileReader;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Namespace;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolTable;

public class MK7ImportSymbols extends GhidraScript {

	@Override
	public void run() throws Exception {
		String[] args = getScriptArgs();
		if (args.length < 3) {
			throw new IllegalArgumentException("usage: MK7ImportSymbols <map> <textEndHex> <bssSizeHex>");
		}
		long textEnd = Long.parseLong(args[1], 16);
		long bssSize = Long.parseLong(args[2], 16);
		layoutMemory(textEnd, bssSize);

		SymbolTable table = currentProgram.getSymbolTable();
		int named = 0, failed = 0;
		try (BufferedReader reader = new BufferedReader(new FileReader(args[0]))) {
			String line;
			while ((line = reader.readLine()) != null) {
				String[] cols = line.split("\t", 3);
				if (cols.length < 2) {
					continue;
				}
				Address addr = toAddr(Long.parseLong(cols[0], 16));
				String[] path = cols[1].split("\u001f");
				try {
					Namespace ns = currentProgram.getGlobalNamespace();
					for (int i = 0; i < path.length - 1; i++) {
						ns = table.getOrCreateNameSpace(ns, path[i], SourceType.IMPORTED);
					}
					String leaf = path[path.length - 1];
					boolean isCode = addr.getOffset() < textEnd;
					if (isCode) {
						Function f = getFunctionAt(addr);
						if (f == null) {
							disassemble(addr);
							f = createFunction(addr, null);
						}
						if (f != null) {
							f.getSymbol().setNameAndNamespace(leaf, ns, SourceType.IMPORTED);
						}
						else {
							table.createLabel(addr, leaf, ns, SourceType.IMPORTED);
						}
					}
					else {
						Symbol primary = table.getPrimarySymbol(addr);
						if (primary == null || primary.getSource() == SourceType.DEFAULT) {
							table.createLabel(addr, leaf, ns, SourceType.IMPORTED);
						}
						else {
							primary.setNameAndNamespace(leaf, ns, SourceType.IMPORTED);
						}
					}
					if (cols.length == 3 && !cols[2].isEmpty()) {
						setPlateComment(addr, cols[2]);
					}
					named++;
				}
				catch (Exception e) {
					failed++;
					if (failed <= 20) {
						println("could not name " + addr + " '" + cols[1].replace('\u001f', ':') + "': " + e);
					}
				}
			}
		}
		println("MK7ImportSymbols: named " + named + ", failed " + failed);
	}

	private void layoutMemory(long textEnd, long bssSize) throws Exception {
		Memory mem = currentProgram.getMemory();
		MemoryBlock first = mem.getBlock(currentProgram.getMinAddress());
		Address split = toAddr(textEnd);
		if (first.contains(split) && !first.getStart().equals(split)) {
			mem.split(first, split);
			MemoryBlock text = mem.getBlock(currentProgram.getMinAddress());
			text.setName(".text");
			text.setPermissions(true, false, true);
			// .rodata and .data cannot be told apart without the exheader, so the
			// whole thing stays writable: the decompiler must not fold its values.
			MemoryBlock data = mem.getBlock(split);
			data.setName(".data");
			data.setPermissions(true, true, false);
		}
		if (mem.getBlock(".bss") == null && bssSize > 0) {
			Address bssStart = currentProgram.getMaxAddress().add(1);
			MemoryBlock bss = mem.createUninitializedBlock(".bss", bssStart, bssSize, false);
			bss.setPermissions(true, true, false);
		}
	}
}
