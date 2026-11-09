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
