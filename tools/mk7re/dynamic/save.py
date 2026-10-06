"""Keep the game (eur2) from writing anything to its save or other files, so
that every boot starts from the same save: `mk7 emu start` writes these
patches at the game's first instruction unless `--save` is given.

Two levels:
- The save data (`data:` archive: system data, ghosts) is written only by
  System::SaveDataManager's thread, through System::BackupManager::write and
  ::move (INITIALIZE moves a backup back in place, SAVE_SYSTEM, SAVE_GHOST and
  FORMAT write). Both return at once with success (0 in the result they
  return through r0), so the game goes on as after a save.
- Anything else the game writes through FS:USER (extdata, ...) goes through
  the SDK's IPC wrappers, one per command (found by the command header in
  their literal pool). The mutating ones return success (nn::Result 0)
  without sending the request; File::Write also reports every byte written.

The game's state in memory changes as usual (unlocks, trophies, records stay
for the rest of the run); only the files do not.

Not covered: the StreetPass box (cecd, under the system's CEC data). The
game deletes and rebuilds its box when it opens the channel and updates it
at boot; faking those writes left the box inconsistent and the channel
showed "SD Card error.". The box holds the outgoing message and its info,
which the game rebuilds from its own state, and nothing is ever received in
the emulator, so the game's state does not depend on it.
"""
NOP_SUCCESS = (0xE3A00000, 0xE12FFF1E)                 # mov r0, #0; bx lr
SRET_SUCCESS = (0xE3A01000, 0xE5801000, 0xE12FFF1E)   # mov r1, #0; str r1, [r0]; bx lr
# (address, what, original words, patched words)
SAVE_PATCHES = (
    (0x00443858, "System::BackupManager::write", (0xE92D43F0, 0xE24DD03C, 0xE1A05000), SRET_SUCCESS),
    (0x00443448, "System::BackupManager::move", (0xE92D40F0, 0xE1A04000, 0xE24DD09C), SRET_SUCCESS),
    # File::Write (0x08030102)(handle, u32 *written, u64 offset, buffer, size, option): *written = size
    (0x00188FEC, "FS File::Write IPC", (0xE92D41F0, 0xE28D401C, 0xE1A05001, 0xE8940042),
     (0xE59D2004, 0xE5812000, 0xE3A00000, 0xE12FFF1E)),   # ldr r2, [sp, #4]; str r2, [r1]; mov r0, #0; bx lr
    (0x00188BA8, "FS:USER CreateFile IPC (0x08080202)", (0xE92D5FF0, 0xE28D4028), NOP_SUCCESS),
    (0x00188C04, "FS:USER DeleteFile IPC (0x08040142)", (0xE92D41F0, 0xE28D4018), NOP_SUCCESS),
    (0x00188C54, "FS:USER RenameFile IPC (0x08050244)", (0xE92D5FF0, 0xE28D402C), NOP_SUCCESS),
    (0x00188D48, "FS:USER FormatSaveData IPC (0x084C0242)", (0xE92D5FF0, 0xE28D4028), NOP_SUCCESS),
    (0x00188DA0, "FS:USER CreateDirectory IPC (0x08090182)", (0xE92D47F0, 0xE28D4020), NOP_SUCCESS),
    (0x00188DF4, "FS:USER CreateExtSaveData IPC (0x08510242)", (0xE92D47F0, 0xE28D4020), NOP_SUCCESS),
    (0x00188E50, "FS:USER DeleteExtSaveData IPC (0x08520100)", (0xE92D4010, 0xEE1D4F70), NOP_SUCCESS),
)


def write_nosave(g, on=True):
    """Write the patches (or restore the code, on=False) through a connected
    GdbClient. `mk7 emu start` calls it at the game's first instruction."""
    for addr, what, orig, patched in SAVE_PATCHES:
        cur = tuple(g.u32(addr + 4 * i) for i in range(len(orig)))
        if cur not in (orig, patched):
            raise RuntimeError(f"unexpected code at {addr:#x} ({what}); not the eur2 build?")
    for addr, _, orig, patched in SAVE_PATCHES:
        for i, word in enumerate(patched if on else orig):
            g.w32(addr + 4 * i, word)


def saving_disabled(mem) -> bool:
    """Whether the patches are in place (read through RPC)."""
    return all(tuple(mem.u32(a + 4 * i) for i in range(len(p))) == p for a, _, _, p in SAVE_PATCHES)
