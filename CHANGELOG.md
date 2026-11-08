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
- The API surface — a full scan shows the pure-C API passes exactly **one** struct by value;
  everything else goes by pointer.

**New in the repository:**

- `spike/day0-abi/` + `scripts/measure-abi.sh` — the ABI measurement probe. It encodes
  `sizeof` / `alignof` / `offsetof` as global array lengths and reads them back out of the
  symbol table, then disassembles the call sites.
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
