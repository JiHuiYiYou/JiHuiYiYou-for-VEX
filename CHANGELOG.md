# Changelog

> **Convention** — same as the
> [compiler repository](https://github.com/JiHuiYiYou/JiHuiYiYou-compiler): one umbrella
> changelog per version axis, which is this file. A `vX.Y+.Z` ship adds a section here; it
> does **not** create a separate `changelog-vX.Y.Z.md`.
>
> **This repository has no releases.** It is a probe: its output is a written spec plus a
> golden reference, not a shipped artifact. There is no `VERSION` file and nothing to bump.

## Unreleased

### Unreleased — Step 0: every unknown on the VEX side turned into a measured value

The deliverable of Step 0 is a spec ([`docs/00-事实基线.md`](docs/00-%E4%BA%8B%E5%AE%9E%E5%9F%BA%E7%BA%BF.md))
and a golden reference, not code.

**The binding surface is one table now, and Day 3's comparison artifacts all build.**

`spike/binding/binding_surface.py` is the single source of truth for the binding surface:
per function it records the **JHYY declaration**, the **exact C prototype** (copied verbatim
from the SDK) and the **ABI** (which registers, how wide the return is, whether it needs
masking). Both emitters — route A (AST → C) and route B (AST → ARM assembly) — read that
table, so the two routes cannot drift apart, and `--check-sdk` compares it verbatim against
the SDK headers.

That was not cosmetic. Emitting prototypes from the JHYY-side signature alone produced
**four `conflicting types` errors** against `v5.h`: `char *` vs `V5_DeviceT`, `int32_t` vs
a 1-byte enum, and `char *` vs `const char *`. With the exact prototypes in the table, the
**C compiler becomes the binding surface's ABI checker**.

`spike/day3-cmp/` is Day 3's behaviour comparison: **the same logic written three ways** —
route A (JHYY → C), route B (JHYY → ARM machine code, *the same JHYY source*), and a
hand-written C++ reference using the `vex::` classes. All three build, and every static
check passes: the binding-surface object is **byte-identical across all three** (and with
the golden reference), the entry symbol is a plain unmangled `main`, route B is ARM-state
with no VFP at all, and routes A and B call **the same functions in the same order**.
What is left is the behaviour itself — three photos of the Brain screen.

Two smaller findings are in the spec too: clang's `-Os` **tail-merges** calls with the same
shape (so comparing call *counts* is the wrong gate — compare the call *set* and *order*),
and a 1-byte enum return leaves the top three bytes of `r0` undefined, so route B must mask
them (the `and r0, r0, #0xff` is in the artifact).

**Routes A and B now agree on behaviour on the PC — and that gate found two real bugs.**

The static gates compare the *call set and order*, which cannot see logic errors. So route B
(a bare-metal image) had **no behavioural verification at all** on the PC. It now does:
`spike/vex-mock/arm_sim.py` is a **small interpreter** for the 18 instructions the emitter
actually emits, so route B runs on the host too, and `spike/vex-mock/diff-ab.sh` compares
route A (C + the C mock) against route B (the interpreter + a Python mirror of the mock) —
**call trace line by line, screen text verbatim**. The two traces match (33 lines) and the
screen text matches.

That gate caught **two real bugs**, both of which would have wasted the lab trip:

1. **Comparisons had their operands swapped.** The emitter put the *right* operand in `r0`
   and the *left* one in `r1`, so `cmp r0, r1` computed `right - left` and every `<` / `>`
   was inverted. On the robot, `v2 < 0` would have been evaluated as `v2 > 0`, so route B
   would have printed `REVF SAME` while routes A and the C++ reference printed `REVF FLIP`.
2. **The epilogue never restored the stack frame.** `ldm sp!, {r4-r11, pc}` reads the return
   address *from `sp`*, so without `add sp, sp, #N` first, the return address came out of the
   local-variable area — the program would have jumped to garbage and hung (a blank screen,
   which looks exactly like "the program crashed").

A third lesson: **the differential gate must compare the screen text, not just the trace.**
Bug ① leaves the *trace* byte-identical (the same four display calls) and only changes the
*words on the screen*.

The interpreter is deliberately small and deliberately loud: an unknown instruction or an
out-of-range access raises instead of being skipped, because a silently-skipped instruction
would make the gate permanently green. It has its own self-test
(`python spike/vex-mock/arm_sim.py --self-test`), wired into the CI gate.

**The GUI flashing path is ready.** The three Step 3 projects now carry `.v5code` files —
the same role `day0-lab.v5code` plays — so the lab trip is "double-click, Download, take a
photo", exactly as last time. Measured against the installed VEXcode Pro V5: it **never
overwrites** an existing project's `makefile` / `vex/mkenv.mk` / `vex/mkrules.mk` (the whole
app bundle mentions `mkenv.mk` only three times: existence check, file-tree order, file-tree
visibility), so route B's extra `.s` rule survives into the GUI build; the SDK version in the
`.v5code` matches the installed one, so no "update old project" prompt appears; the project
name does not affect the artifact's bytes; and even if the GUI auto-generates
`robot-config.*`, the binary is unchanged (`--gc-section` drops the unreferenced empty
`vexcodeInit`). See spec § 2.3.

**One real compiler bug found and filed — and one of our own findings retracted.**

Reading the main repo's AST dump while building the VEX target turned up a **real bug in
the compiler's dump tool**: `jhyy dump` prints a float literal's bit pattern with
`ad_kv_hex64()`, which computes `87 + (nib - 10)` for nibbles >= 10. `'a'` is 97, so
every hex digit from `a` upwards comes out as `W`, `X`, `Y`, `Z`, `[`, `\` — the bit
pattern is wrong *and* the output is not valid hex. The convention is confirmed by the
two other implementations in the same repo: the IL decoder in `compiler/src0/ir.jhyy`
uses `hex - 87` (correct) and the IL encoder in `compiler/src0/codegen.jhyy` uses
`48 + nib` plus 39 (also correct) — so this one site is simply off by ten. Filed as
**W-227** in the main repo's ledger (`JiHuiYiYou/docs/internal/workarounds.md`), with the
one-character fix noted; the fix itself is a release-level change (editing `compiler/src0/*.jhyy`
shifts the self-hosted artifact) and is therefore not done from this repository.

**One of our own recorded findings was wrong and has been retracted.** We had written
down that the AST dump "loses" a backslash in string literals, and had accordingly
excluded backslash strings from the corpus. Re-measuring on 2026-11-14: the dump is
**lossless** — the parser stores the escaped text verbatim and the dump prints it
verbatim, byte for byte. The original observation was a **test artifact**: the corpus
file had been written through a shell heredoc, which ate one backslash, so the "source"
we compared against was already missing it. The corpus now contains a double-backslash
case (the gate compares our emitter's output against the main compiler's, run for real),
and the emitter's self-test covers both shapes. The lesson is recorded next to the case:
write backslash-bearing fixtures with the editor tools, never through a heredoc.

**Day 1–2 has started: the C emitter's first closed loop works.**
`spike/day1-emit/` reads the main repo's `jhyy dump` (its AST tree, already machine-parseable)
and emits C. The main repo is untouched — the bypass is real from the first commit. The same
`hello.jhyy` compiled both ways — through the main repo's own compiler (the yardstick) and
through the emitter — produces **byte-identical stdout and the same exit code**.

**And the first real A-route product exists:** `spike/day1-emit/vex_demo.jhyy` — the first
program written in actual JHYY — compiles through the emitter into a V5 binary
(`day1vex.bin`, 2516 B). Its binding-surface object is **byte-identical to the golden
reference's**, so the JHYY route and the hand-written C route provably call the same symbol.
The entry symbol is a plain, unmangled `main`, which is what VEX's `vexMain` looks up.

**Everything that still needs hardware is now one trip:** `docs/第1步-上机清单.md`,
and `scripts/lab-prep.sh` builds every artifact before you leave. The emitter also grew a
**corpus** (`spike/day1-emit/corpus/`) so coverage is measurable rather than anecdotal — it
already caught a bug in the test program itself, and the emitter now handles `else`,
arrays and indexing (slices are refused on purpose: C has no slices, so the length would
silently be lost).

**The B-route plumbing works:** `scripts/overlay-build.sh` copies the pinned main-repo tree
into a shadow directory, overlays this repo's `spike/overlay/*.jhyy`, and builds a working
compiler there — the main repo's working tree is never touched. The ARM backend has
somewhere to land now.

**And route B itself now works as a probe:** `spike/route-b/` turns a JHYY program into
**ARM assembly** (not C) and builds a V5 binary from it — `routebvex.bin`, 2580 B, ARM-state
4-byte instructions, no VFP at all (so softfp holds by construction). The binding-surface
object is **byte-identical across all three routes** — the golden reference, route A and
route B — so all three provably call the same symbol. Because the emitter picks the
registers and widths itself, the two shared-layer pointer-width spots in the compiler are
**bypassed entirely**: the prototype needs no compiler patch, and the decision of whether
to add a real ARM backend to the compiler can be deferred.

**The repository's relationship to the language main repo is now fixed: permanent bypass.**
The main repo keeps the language; this repo keeps the VEX target support. Nothing is pushed back
into the main repo, and the main repo's working tree is never touched — the compiler is consumed
read-only, pinned to a commit, through a shadow build. The spec records the pin, the upstream
sync duty, and the one gate this repo owes its own bypassed files
([`docs/第0步-验收线.md` § 3.4](docs/%E7%AC%AC0%E6%AD%A5-%E9%AA%8C%E6%94%B6%E7%BA%BF.md)).

**First on-robot session (2026-11-09) — all eight spec items now measured:**

- **Tick frequency = 100 Hz.** `vexDelay(1)` really takes **10 ms** (50 calls = 500 ms), so the
  scheduler tick is 10 ms; `vexDelay(0)` takes **0 ms** — it does not yield at all.
- **The whole 1 MB heap is free** at startup and `_sbrk` allocates, writes and reads back — but the
  SDK's libc still ships **no allocator**, so JHYY needs its own bump allocator over `_sbrk`.
- **Motor units, finally:** velocity is **RPM** of the output shaft, position is **degrees** of the
  output shaft (°/s = RPM × 6). Setting 50 and spinning for a second moves ~270°, not 50°.
- **A device handle being non-NULL does not mean a device is plugged in** — all four ports returned
  a handle while only one had a motor.
- The competition-status **bit meanings** were recovered statically from the SDK's own C++
  (`vex::competition`), so no hardware is needed for them any more.
- The probe's own lessons (a lost log page, invisible text in the same colour as its background, a
  button that was never polled) are written up in the spec as well.
- **The display semantics are settled too**: the screen is **480×272** (which matches the SDK's own
  `SYSTEM_DISPLAY_WIDTH/HEIGHT` — a human observation and a header constant cross-check each
  other), pixel coordinates start at the **top-left**, the **text API is in pixels** too, and
  **`bOpaque=0` is transparent while `bOpaque=1` paints the background over it**. The binding
  surface therefore uses **`bOpaque=1`**: white-on-black, always readable. (Transparent was the
  trap that made text vanish on a coloured block.)

**Measured and written down** (all on this machine, zero JHYY variables):

- Binary format — the SDK's `objcopy` emits the final format directly; `XVX5` + version 1
  in the first 32 bytes, entry at `0x03800020`.
- Startup chain — closed end to end, from `vexStartup` to `vexMain` to the user's task.
- Concurrency model — the user's `main` is a task registered by `vexTaskAdd`, so route B
  must emit a plain, unmangled `main` symbol.
- ABI — locked to **softfp**, matching `libv5rt.a` in both directions.
- Instruction set — ARM state, fixed 4-byte instructions; no Thumb-2 encoding needed.
- Struct layouts — measured `sizeof` / `alignof` / `offsetof` for the bound types, and the
  register convention for by-value structs and 1-byte enums.
- The heap — the SDK's libc subset ships **no allocator at all**: no `malloc`, `free`,
  `calloc`, `realloc` or `sbrk`. The only heap primitive is `_sbrk`, which advances a break
  between `_heap_start` and `_heap_end` and returns -1 past the end. ⇒ how much of the 1 MB
  is actually free when the program starts is an **on-robot** fact, not a static one.
- The API surface — a full scan shows the pure-C API passes exactly **one** struct by value;
  everything else goes by pointer.

**New in the repository:**

- `spike/binding/binding_surface.py` — the binding-surface table: the JHYY declaration, the
  exact C prototype and the ABI of every bound function, with a self-test and a
  `--check-sdk` mode that compares the table against the SDK headers verbatim.
- `spike/day3-cmp/` — the behaviour comparison: one JHYY source compiled two ways plus a
  C++ reference, and the static checks that prove the two routes line up before the robot
  ever sees them.
- `scripts/self-test.sh` — the self-test gate for this repository's Python tools (AST
  parser, route-A emitter, route-B emitter, binding-surface table). It needs no VEXcode Pro
  V5, so it runs on CI.
- `spike/day0-abi/` + `scripts/measure-abi.sh` — the ABI measurement probe. It encodes
  `sizeof` / `alignof` / `offsetof` as global array lengths and reads them back out of the
  symbol table, then disassembles the call sites.
- `spike/day0-lab/` — the **on-robot measurement probe**. The five gaps in the spec that
  only hardware can close (tick frequency, display coordinate / `bOpaque` semantics, how much
  of the 1 MB heap is actually free, the competition-status bits, and the motor behaviour
  itself) are measured in **one flash**. It reuses `day0-c`'s binding surface instead of
  copying it, and carries no `__DATE__` / `__TIME__`, so its `.bin` stays byte-reproducible
  and hash-listed like the golden reference.
- The probe is a **real VEXcode project** (`day0-lab.v5code` + the same `makefile` / `vex/`
  the GUI generates), so it can be opened and downloaded from the GUI like any other
  project — the command line is only there for reproducibility and the hash list.
- **The probe records itself — over three channels, because an SD card is not a given.**
  The same `key=value` log goes to the SD card (`day0lab.txt`, via newlib's `fopen`,
  which the SDK's own `sdcard::savefile` proves is wired straight to the card), to the
  Brain console (visible in VEXcode's terminal pane), and to the screens (paged
  replay, so a photo carries the whole thing). The probe says out loud which channel
  worked. The few things only a human can judge — the display's coordinate system, what
  `bOpaque` really does, whether the motor actually moved — the probe **asks** as
  multiple-choice questions on the controller, and **writes the answers into the same
  log**. So the human only presses buttons; nobody writes down a number.
- Motor **direction** is deliberately *not* a question: clockwise depends on which end
  you look from and which side of the robot the motor sits on — that is installation,
  not API. The probe settles the direction semantics itself with three sign experiments
  (`+50`, `-50`, and the SDK's reverse flag) and only asks whether the motor moved.
- `scripts/parse-lab-log.py` — turns `day0lab.txt` into the observation record that goes
  into the spec, with the readings spelled out and anything not measured marked as
  *not measured* (the acceptance line never gets ahead of the fact baseline). Ships with
  `--self-test`.
- `spike/day0-c/include/jhyy_vex.h` — the JHYY binding surface, including
  `jhyy_vex_display_puts`, a **non-variadic** display wrapper. JHYY cannot call variadic
  functions, so both routes must call one fixed-signature symbol.
- `scripts/check-docs.py` — the docs gate, including a self-test that breaks the docs on
  purpose and asserts every check fires.
- `scripts/check-artifacts.sh` — the artifact gate: rebuilds the golden reference from a
  clean tree and checks it against the hash list in the spec.

**Housekeeping:**

- The repository-level documents (`README.md`, `CONTRIBUTING.md`, `SECURITY.md`,
  `CODE_OF_CONDUCT.md`, the issue templates and the PR template) are now in **English**,
  matching the rest of the family; `docs/` and `README.zh-CN.md` stay in Chinese.
- A `README.zh-CN.md` mirrors `README.md` — **change one, change both**.
- The GitHub *About* description, homepage and topics now follow the family conventions.
