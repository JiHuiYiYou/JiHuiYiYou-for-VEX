# Security Policy

**JHYY for VEX** is a research probe maintained by one person. It produces **no releases**
and **no artifacts** — but it does produce `.bin` files that link proprietary VEX code, and
that is the security-relevant fact this page is mostly about.

If you only want the short version:

> **The artifacts contain VEX-proprietary code. Do not redistribute them.**
> **Do not open a public issue for a suspected vulnerability** — use
> [the private advisory form](https://github.com/JiHuiYiYou/JiHuiYiYou-for-VEX/security/advisories/new).

---

## 1. The redistribution problem — read this first

A `.bin` or ELF produced by this repository links the official VEX SDK's `libv5rt.a`.
That library contains **VEX-proprietary code**, and VEX's SDK carries a restrictive
redistribution EULA.

**If you obtained an artifact from this repository and intend to redistribute it** — publish
it, upload it, attach it to something, bundle it for someone else:

> **Do not publish it yet.** The current position and the open question are recorded in
> [`docs/00-事实基线.md` § 14](docs/00-%E4%BA%8B%E5%AE%9E%E5%9F%BA%E7%BA%BF.md).

The **source** of this repository is MIT and freely reusable. The **artifacts** are not —
those are two separate things.

This repository does **not** redistribute the VEX SDK. Install it through VEX's own channel.

## 2. Reporting a vulnerability

**Do not open a public issue for a suspected vulnerability.** Public issues are indexed,
mirrored and cached within minutes — a public report can turn a fix into an exploit before a
patch exists.

Use GitHub's private advisory flow:

**→ https://github.com/JiHuiYiYou/JiHuiYiYou-for-VEX/security/advisories/new**

It opens a thread visible only to you and the maintainer. If that form is unavailable to
you, email the maintainer at **15901598712@163.com** with the same information and ask for a
receipt confirmation.

Please include:

| Item | Why it matters |
|---|---|
| **What the spec says** — the § number and the quoted text | fixes land on the newest wording first |
| **What you observed** — the raw command output, unedited | a one-line diff is the difference between a same-day fix and a week of questions |
| **The command line** — the exact invocation | |
| **The environment** — VEXcode Pro V5 version, `clang --version`, platform | the toolchain version changes what the flags mean |
| **Impact** — what does an attacker gain, and what must they already have | it decides severity, and severity decides the deadline |

> [!TIP]
> **Capture exit codes with a harness or Python `subprocess`, not by reading `$?` in MSYS2
> bash.** Bash truncates exit codes to 8 bits (`value & 0xFF`), so an expected code ≥ 256 has
> to be reduced before you compare it (827 → 59, 501 → 245, 300 → 44, 1000 → 232).

> [!NOTE]
> **You do not need to prove exploitability.** A source-level demonstration is enough.

---

## 3. What counts as a vulnerability here

### In scope

- **Redistribution of the artifacts.** A `.bin` or ELF published somewhere it should not be,
  or advice given to others that leads them to publish one. The artifacts embed VEX's
  proprietary runtime; the EULA question is unresolved and open (see § 1).
- **Supply-chain hazards introduced by this repository.** A script here that downloads
  something, resolves a toolchain from an untrusted location, or executes bytes that were
  not part of the checked-out source.
- **The build scripts executing something the user did not intend.** `scripts/build-vex.sh`
  drives the VEXcode Pro V5 toolchain; `scripts/check-artifacts.sh` runs it. A crafted
  project directory that makes them do something outside their documented scope counts.
- **A published hash or measurement that does not match reality**, in a way that would cause
  someone to trust the wrong artifact.

### Out of scope

- **Documentation drift.** A wrong number, a stale claim, a broken link — that is a
  **correctness** problem, not a security one. Report it as a normal issue; the
  [contribution guide](CONTRIBUTING.md) has the format that makes such a report actionable.
- **Build scripts that fail to run** on your machine. Normal issue.
- **The JHYY language's own behaviour.** Report that in the
  [compiler repository](https://github.com/JiHuiYiYou/JiHuiYiYou-compiler).
- **VEX firmware, hardware, or the official SDK's own vulnerabilities.** Report those to
  VEX.
- **Bugs in the tools this repository drives** (clang, `ld`, `objcopy`) beyond the bundling
  itself.

---

## 4. Supported versions

| Line | Supported |
|---|---|
| **The current `main`** | ✅ the only line that exists — there are no releases |
| Anything older | ❌ — the spec is rewritten in place; there is no version history to support |

This page deliberately names **no version numbers**: this repository has no releases, and the
spec moves in place.

---

## 5. What happens after you report

| Stage | Target |
|---|---|
| Acknowledgement that the report was received | 7 days |
| Triage — is it a vulnerability, and how severe | 14 days |
| Mitigation published, if one exists independently of a fix | immediately — you will not be asked to keep it quiet |
| Fix landed for a critical or high severity report | as soon as it is green in CI — no fixed date, but nothing is deliberately held back |

These are **targets, not guarantees** — this is a one-person project with a day job.
If a report is not acknowledged inside the window, that is a defect in this process: say so
in the same thread, and treat the silence as worth escalating.

You will be told the triage outcome even when the answer is "not a vulnerability" — a
reasoned "no" is a real answer, and it is more useful to you than silence.

---

## 6. Disclosure

- **Give the maintainer a reasonable window to publish a fix before disclosing publicly.**
  The default expectation is **90 days** from the first report. Ask for more time if a fix
  needs it; an explicit extension is fine.
- **If a mitigation exists before the fix does** — for example "do not redistribute the
  artifact" — it is published in the advisory immediately.
- **Credit** is offered in the advisory. Say so if you would rather stay anonymous.
- **Already public?** If the issue is already described somewhere public, say so in the
  report — it changes the disclosure timeline, not whether it gets fixed.

---

## 7. Security-relevant properties of this project

Facts a reader should know, because they change what "vulnerable" means here.

- **The artifacts embed VEX-proprietary code.** They are the reason this page exists. The
  repository never commits them; it stores them locally and verifies them against a hash
  list (see [`docs/00-事实基线.md` § 2.1](docs/00-%E4%BA%8B%E5%AE%9E%E5%9F%BA%E7%BA%BF.md)).
- **The VEX SDK is not vendored here.** The scripts expect it to be installed by VEX's own
  installer, at the standard path.
- **The scripts download nothing.** `scripts/build-vex.sh` drives a locally installed
  toolchain; `scripts/measure-abi.sh` compiles one file into a temp directory and deletes
  it; `scripts/check-docs.py` and `scripts/check-artifacts.sh` read the repository and the
  local toolchain. None of them opens a socket.
- **`scripts/check-artifacts.sh` executes the build**, which means it executes the toolchain
  and links the SDK. Treat the SDK as part of your trust boundary, exactly like the build
  itself.
- **There is no telemetry and no credential handling** anywhere in this repository.

---

## 8. Reporting something that is not a vulnerability

- **A measurement that contradicts the spec** → a normal issue. The
  [contribution guide](CONTRIBUTING.md) has the format that makes such a report actionable.
- **A question about the VEX API or the plan** → a normal issue or a discussion.
- **A known limitation you want to work on** → the "to be measured" list in
  [`docs/00-事实基线.md` § 13](docs/00-%E4%BA%8B%E5%AE%9E%E5%9F%BA%E7%BA%BF.md) is the
  shortest path to doing something useful.
- **A JHYY language question** → the
  [compiler repository](https://github.com/JiHuiYiYou/JiHuiYiYou-compiler).
