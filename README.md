<div align="center">

<div><img src="assets/icon-animated.svg" width="96" alt="JHYY logo"></div>

<div><img src="assets/jhyy-calligraphy.png" width="220" alt="机会翼游 calligraphy logo"></div>

### JHYY for VEX — An embedded target for the JHYY (机会翼游) systems programming language

**Compile JHYY to the VEX V5 Brain. Measured, not guessed.**

[![Day 0](https://img.shields.io/badge/Day%200-spec%20done-00d4aa)](docs/%E7%AC%AC0%E6%AD%A5-%E9%AA%8C%E6%94%B6%E7%BA%BF.md)
[![Spec](https://img.shields.io/badge/spec-single%20source%20of%20truth-blue)](docs/00-%E4%BA%8B%E5%AE%9E%E5%9F%BA%E7%BA%BF.md)
[![Route](https://img.shields.io/badge/route-B%20direct%20ARM%20machine%20code-lightgrey)](#route)
[![CI](https://github.com/JiHuiYiYou/JiHuiYiYou-for-VEX/actions/workflows/ci.yml/badge.svg)](https://github.com/JiHuiYiYou/JiHuiYiYou-for-VEX/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![中文](https://img.shields.io/badge/lang-%E4%B8%AD%E6%96%87-red)](README.zh-CN.md)

[Route](#route) · [Status](#status) · [What Day 0 measured](#what-day-0-measured) · [Gates](#gates) · [Layout](#layout) · [Docs](#docs) · [License](#license)

</div>

---

## What it is

**JHYY for VEX** gives [JHYY (机会翼游)](https://github.com/JiHuiYiYou/JiHuiYiYou-compiler) — a
self-hosted, statically typed, expression-oriented systems language — an **embedded target**:
the VEX V5 Brain (ARM, Xilinx Zynq / Cortex-A9).

The target machine is not the hard part. The hard part is that **everything about the VEX side
starts out unknown**: the binary format, what the startup code does to you, which ABI the
official SDK actually speaks, how its structs are laid out, and which functions are safe to
call from another language.

So **Step 0 turns those unknowns into measured values** and writes them down as a spec — which
is then the golden reference for the real work.

```
Step 0 (now)  Hand-written C probe → binary format / startup chain / ABI / API surface, all measured
               ├─ JHYY → C → clang → .bin          (route A, the golden reference)
               └─ JHYY → ARM machine code → .bin    (route B, the goal)
```

## Route

The goal is **route B: JHYY emits ARM machine code directly** — not "transpile to C++".

**Route B replaces clang's slot. It does not replace the SDK.** Everything from `ld` down stays
exactly as it is:

```
                ┌─ route A: JHYY → C source → clang ──┐
JHYY source ────┤                                    ├─→ arm-none-eabi-ld
                └─ route B: JHYY → ARM machine code ──┘      │
                                                               ├─ lscript.ld      official SDK
                                                               ├─ stdlib_0.lib    official SDK
                                                               ├─ libv5rt.a       official SDK
                                                               └─ objcopy → .bin  official SDK
```

**Route B = JHYY emits an ARM `.o`, the official SDK links it into a `.bin`.**

That is structurally the same as what pros-rs did years ago (Rust emits `.o`, links libpros) —
the difference is that this route is being re-walked **with measurements in hand**, without
their sunk cost.

⇒ The consequences are the same too: **the ABI must be locked** (softfp), **the entry symbol
must be locked** (plain `main`), and **the binding surface must be locked** (every `extern fn`
maps one-to-one onto a C symbol). Link a different library and you get a different ABI — leave
any of the three unlocked and the two routes cannot be compared against each other.

## Status

| | |
|---|---|
| Step 0 | ✅ **Spec done** — **all 8 spec items measured**, the last one on a real Brain on 2026-11-09 (tick frequency = **100 Hz**). The display details (`bOpaque`, the text coordinate unit) are still open — the probe is ready: [`spike/day0-lab/`](spike/day0-lab) |
| Step 1–2 | 🔶 **Emitter emits C — first closed loop done** (2026-11-10): the same `hello.jhyy` compiled through the main repo's compiler and through this repo's emitter gives **byte-identical output and the same exit code**. Next: the VEX `.bin` and a real Brain run — [`spike/day1-emit/`](spike/day1-emit) |
| Route B | 🔶 **Direct ARM machine code works as a probe** (2026-11-10): [`spike/route-b/`](spike/route-b) emits ARM assembly instead of C; the binding-surface object is **byte-identical across all three routes** |
| Step 3 | 🔶 **All three comparison artifacts build** (2026-11-10): **the same logic** written three ways (JHYY→C / JHYY→machine code / hand-written C++), and every static check passes — the binding-surface object is **byte-identical across all three**, the entry symbol `main` is unmangled, route B is ARM-state with no VFP, and **routes A and B call the same functions in the same order**. Next: one lab trip — [`spike/day3-cmp/`](spike/day3-cmp) |
| Route B | ⬜ JHYY's ARM backend |

### The binding surface is one table

Every `extern fn` has to answer three questions at once: **how JHYY writes it**,
**what prototype C gets**, and **how AAPCS passes it**. Those used to live in three
places, so they drifted — measured: emitting prototypes from the JHYY-side signature
alone produced **4 × `conflicting types`** against `v5.h`.

⇒ They are now **one table**: [`spike/binding/binding_surface.py`](spike/binding/binding_surface.py) —
**both the route-A and the route-B emitter read it**, so one edit moves both routes;
`--check-sdk` compares it **verbatim against the SDK headers**.

### The blocker nobody expects

JHYY's ABI v4.0.0 **locks pointer width at 64 bits**, and all four of its targets are amd64 —
**there is no ARM target yet**. But `V5_DeviceT` is a **4-byte** C pointer.

⇒ The ARM target has to settle pointer width at 32 bits **first**. Without that, not even an
`extern fn` lines up. This is the first hard rock of route B; it is written down in the spec
so nobody discovers it the expensive way.

## What Day 0 measured

Everything below was measured on this machine (compile / disassemble / `readelf` / `nm`) —
**zero JHYY variables**. Anything not measured is marked as *to be measured*; no guesses are
written down.

- **The binary format needs no extra converter** — the SDK's `objcopy` emits the final format
  directly. The first 32 bytes are `XVX5` + version 1, and the entry point sits right behind
  them at `0x03800020`.
- **The startup chain is fully closed**: clear `.bss` → stdlib version check → newlib impure
  data → `__libc_init_array` → `vexMain` → `__libc_fini_array`.
- **Your `main` is a task, not the main thread** — the SDK registers it with
  `vexTaskAdd(main, 2, "MAIN")`. ⇒ route B must emit a plain, unmangled `main` symbol.
- **ABI locked to softfp** — our ELF and `libv5rt.a` both lack `Tag_ABI_VFP_args`.
- **The target is ARM state, fixed 4-byte instructions** ⇒ no Thumb-2 variable-length encoding
  needed in the backend.
- **Two API layers**: C++ `vex::` (1404 mangled symbols, deliberately untouched) and the
  **pure-C `vex*()`** — the latter binds straight to JHYY's `extern fn`, with **no glue layer**.
- **Struct layouts measured**: both packed and unpacked exist. The whole pure-C API passes
  exactly **one** struct by value (`V5_DeviceVisionRgb`, ≤4 B ⇒ passed in a register);
  everything else goes by pointer.
- **Memory budget**: 1 MB heap, 14 KB stack — recursion depth is a hard constraint.

## Gates

The gate list lives in exactly one place:
[`docs/第0步-验收线.md` § 6](docs/%E7%AC%AC0%E6%AD%A5-%E9%AA%8C%E6%94%B6%E7%BA%BF.md).

| Gate | Where | What it checks |
|---|---|---|
| Docs gate | CI | Links resolve · `§ N` references resolve · **the acceptance line never gets ahead of the fact baseline** · bare paths resolve |
| Docs-gate self-test | CI | **Proves the gate can go red** — it breaks the docs on purpose and asserts every check fires |
| Shell gate | CI | `bash -n` + `shellcheck` |
| Artifact gate | **local** (needs VEXcode Pro V5) | Rebuilds the golden reference and checks it against the hash / size / magic / entry address recorded in the spec |

```bash
python scripts/check-docs.py              # docs gate
python scripts/check-docs.py --self-test  # docs-gate self-test
scripts/check-artifacts.sh spike/day0-c day0c      # artifact gate (golden reference)
scripts/check-artifacts.sh spike/day0-lab day0lab  # artifact gate (on-robot probe)
```

> The artifact gate is a **local** gate: GitHub's stock runners have no VEXcode Pro V5, and a
> CI gate that is always green is worse than no gate at all.

## Layout

```
jhyy-for-vex/
├── docs/
│   ├── 00-事实基线.md        # ★ the single source of truth for measured facts
│   └── 第0步-验收线.md       # ★ acceptance criteria, decomposition, gate list
├── scripts/
│   ├── build-vex.sh          # build a VEX project from the command line
│   ├── measure-abi.sh        # measure struct layouts and calling conventions
│   ├── check-docs.py         # docs gate (with --self-test)
│   ├── check-artifacts.sh    # artifact gate (rebuild + verify the hash list)
│   ├── self-test.sh          # self-test gate (this repo's Python tools — runs on CI)
│   └── parse-lab-log.py      # the on-robot log → the spec's observation record
├── spike/
│   ├── binding/              # ★ the binding-surface table (single source of truth)
│   │   └── binding_surface.py   #   JHYY decl / exact C prototype / ABI, per function
│   ├── day0-c/               # the Step 0 probe: hand-written C, zero JHYY variables
│   │   ├── include/jhyy_vex.h # ★ the JHYY binding surface
│   │   └── src/jhyy_vex.c     #   non-variadic display wrapper
│   ├── day0-lab/             # the on-robot measurement probe (the five hardware gaps)
│   │                          # — a real VEXcode project: open it in the GUI and Download
│   │                          # — it logs its own results to the SD card
│   ├── day1-emit/            # Step 1–2: the route-A emitter (AST → C) + the gates
│   ├── route-b/              # Step 1–2: the route-B emitter (AST → ARM assembly)
│   ├── day3-cmp/             # Step 3: the same logic three ways + the static checks
│   └── day0-abi/             # the ABI measurement probe
├── .github/
│   ├── workflows/ci.yml
│   ├── ISSUE_TEMPLATE/
│   └── pull_request_template.md
└── CONTRIBUTING.md · SECURITY.md · CODE_OF_CONDUCT.md · LICENSE
```

## Docs

| | |
|---|---|
| [`docs/00-事实基线.md`](docs/00-%E4%BA%8B%E5%AE%9E%E5%9F%BA%E7%BA%BF.md) | The fact baseline — every measured number and platform fact lives here, and nowhere else |
| [`docs/第0步-验收线.md`](docs/%E7%AC%AC0%E6%AD%A5-%E9%AA%8C%E6%94%B6%E7%BA%BF.md) | Acceptance criteria, the step-by-step plan, and the gate list |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to build, which gates to run, and the rules |
| [`SECURITY.md`](SECURITY.md) | Redistribution constraints — **read before shipping an artifact** |
| [`CHANGELOG.md`](CHANGELOG.md) | What changed — this repository has no releases, so this file holds everything |
| [JHYY compiler](https://github.com/JiHuiYiYou/JiHuiYiYou-compiler) | The language, the spec, and the ABI this project targets |
| [Project site](https://jihuiyiyou.github.io/JiHuiYiYou-website/vex/) | The family website |

## License

Source: **MIT** — see [LICENSE](LICENSE).

⚠️ **The artifacts are a separate question.** A `.bin` or ELF produced here links the official
VEX SDK's `libv5rt.a`, which contains **VEX-proprietary code** subject to a restrictive
redistribution EULA. Until that is settled (see the spec's open questions), **do not publish
the artifacts**. The SDK itself is **not** redistributed by this repository.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Short version: facts first, the probe stays a probe,
and the JHYY compiler repository is never edited from here — the main repo keeps the language,
**this repo keeps the VEX target support** (permanent bypass: a pinned, read-only copy of the
compiler plus a shadow build, nothing pushed back). See § 3.4 of the acceptance line.
