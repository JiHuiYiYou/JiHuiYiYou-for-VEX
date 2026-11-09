# Contributing to JHYY for VEX

Thanks for your interest in the VEX embedded target for [JHYY (机会翼游)](https://github.com/JiHuiYiYou/JiHuiYiYou-compiler).

This repository is a **probe**, not a product: its output is a written spec of measured
facts plus a golden reference, not a maintained backend. This guide covers how to run the
gates, how to report something that does not match the spec, and how to get a pull request
merged.

- [Code of conduct](#code-of-conduct)
- [I have a question](#i-have-a-question)
- [Reporting an inconsistency](#reporting-an-inconsistency)
- [Reporting a security vulnerability](#reporting-a-security-vulnerability)
- [Suggesting a change](#suggesting-a-change)
- [Development setup](#development-setup)
- [The gates](#the-gates)
- [Pull request process](#pull-request-process)
- [Conventions](#conventions)
- [License](#license)

---

## Code of conduct

Be respectful. Assume good faith. Technical disagreement is not personal conflict.

The full text — what that means in practice, and how to report a violation — is
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## I have a question

| Question | Where the answer lives |
|---|---|
| What is actually known about the VEX side? | [`docs/00-事实基线.md`](docs/00-%E4%BA%8B%E5%AE%9E%E5%9F%BA%E7%BA%BF.md) — the single source of truth for every number and platform fact |
| What is the plan, and what is the acceptance line? | [`docs/第0步-验收线.md`](docs/%E7%AC%AC0%E6%AD%A5-%E9%AA%8C%E6%94%B6%E7%BA%BF.md) |
| How does JHYY's FFI / calling convention work? | [JHYY ABI v4.0.0](https://github.com/JiHuiYiYou/JiHuiYiYou-compiler/blob/main/docs/abis/jhyy-abi-v4.0.0.md) |
| How do I build, measure, and check? | [Development setup](#development-setup) and [The gates](#the-gates) |
| Why is the probe structured this way? | [`docs/第0步-验收线.md` § 3](docs/%E7%AC%AC0%E6%AD%A5-%E9%AA%8C%E6%94%B6%E7%BA%BF.md) — the "🔒" clauses |

## Reporting an inconsistency

Open an issue and include:

1. **What the spec says** — the exact location (§ number, or file:line) and the quoted text.
2. **What you measured** — the command and its raw output. Do not paraphrase it.
3. **The command line** — the exact invocation that produced that output.
4. **The environment** — VEXcode Pro V5 version, `clang --version`, and the platform.

> [!TIP]
> Capture command output with a harness or Python `subprocess` rather than by reading
> `$?` in MSYS2 bash: bash truncates exit codes to 8 bits (`value & 0xFF`), so an
> expected code ≥ 256 has to be reduced before you compare it (827 → 59, 501 → 245,
> 300 → 44, 1000 → 232).

> [!NOTE]
> **A measurement is the currency here.** If you can close one of the "待测" (to be
> measured) entries in the spec, that is the most useful report this repository can get.
> The [issue template](.github/ISSUE_TEMPLATE/bug_report.yml) is built around that.

## Reporting a security vulnerability

**Do not open a public issue for it.** Use the private advisory form:

**→ https://github.com/JiHuiYiYou/JiHuiYiYou-for-VEX/security/advisories/new**

What counts as a vulnerability here, what to include, and what happens afterwards are all
in [`SECURITY.md`](SECURITY.md).

## Suggesting a change

Say what you would **know** afterwards, not what you would implement — this repository is
a probe, and the spec is the deliverable.

Three rules decide most proposals on their own:

- **Facts first.** If the change adds a measured value, it goes into
  [`docs/00-事实基线.md`](docs/00-%E4%BA%8B%E5%AE%9E%E5%9F%BA%E7%BA%BF.md) with the
  command that produced it. If it adds a plan, it goes into
  [`docs/第0步-验收线.md`](docs/%E7%AC%AC0%E6%AD%A5-%E9%AA%8C%E6%94%B6%E7%BA%BF.md).
- **Do not grow the probe into a product.** A feature request that needs a general
  emitter, a general ABI layer, or a general C binding is out of scope — see
  [`docs/第0步-验收线.md` § 3.1](docs/%E7%AC%AC0%E6%AD%A5-%E9%AA%8C%E6%94%B6%E7%BA%BF.md).
- **Do not edit the compiler repository from here.** The main repo keeps the language;
  **this repo keeps the VEX target support** — a permanent bypass: the compiler is consumed
  read-only, pinned to a commit, through a shadow build, and **nothing is pushed back**. The
  spec records the pin, the upstream sync duty and the gate this repo owes its own bypassed
  files — see
  [`docs/第0步-验收线.md` § 3.4](docs/%E7%AC%AC0%E6%AD%A5-%E9%AA%8C%E6%94%B6%E7%BA%BF.md).

## Development setup

**Host:** Windows 10 + MSYS2 bash (`C:\msys64\usr\bin\bash.exe`).

| Needed | Why |
|---|---|
| **VEXcode Pro V5** | installed at `C:\Program Files (x86)\VEX Robotics\VEXcode Pro V5` — the artifact gate and the ABI measurement both need its toolchain |
| ARM binutils | `C:\msys64\ucrt64\bin\arm-none-eabi-{objdump,readelf,nm}.exe` (`pacman -S mingw-w64-ucrt-x86_64-arm-none-eabi-binutils`) |
| Python 3 | the docs gate |

> [!IMPORTANT]
> **MSYS2's own `objdump` is x86-only.** Pointing it at a VEX artifact gives
> `can't disassemble for architecture UNKNOWN!` ⇒ use `arm-none-eabi-objdump`.
> `readelf` works from either.

```bash
# 1. Build the golden reference
scripts/build-vex.sh spike/day0-c day0c

# 2. Artifact gate — rebuild and check it against the spec
scripts/check-artifacts.sh spike/day0-c day0c

# 3. Measure struct layouts and calling conventions
scripts/measure-abi.sh

# 4. Docs gate
python scripts/check-docs.py
python scripts/check-docs.py --self-test
```

> [!NOTE]
> The VEX SDK is **not** redistributed by this repository. Install it through VEX's own
> channel — see [`SECURITY.md`](SECURITY.md).

## The gates

The gate list lives in exactly one place:
[`docs/第0步-验收线.md` § 6](docs/%E7%AC%AC0%E6%AD%A5-%E9%AA%8C%E6%94%B6%E7%BA%BF.md).
Do not restate it elsewhere.

### CI gates — these really run on a stock runner

| Gate | Command | What it checks |
|---|---|---|
| Docs gate | `python scripts/check-docs.py` | Links resolve · `§ N` references resolve · **the acceptance line never gets ahead of the fact baseline** · bare paths resolve · **the `.github/` YAML parses** |
| Docs-gate self-test | `python scripts/check-docs.py --self-test` | Injects five kinds of breakage and asserts every check fires — **a gate that was never seen to fail is not a gate** |
| Shell gate | `bash -n scripts/*.sh` + `shellcheck -x scripts/*.sh` | Script syntax and common traps |

> [!NOTE]
> The YAML check needs `pyyaml`. CI installs it; locally use
> `C:\Users\liuzhen\miniconda3\python.exe` (the `python` on `PATH` is MSYS2's, which
> has no `pip` and no `pyyaml`). Without it, the gate says it **skipped** the YAML check
> rather than pretending it passed.

### Local gates — CI cannot run these

| Gate | Command | What it checks |
|---|---|---|
| Artifact gate | `scripts/check-artifacts.sh spike/day0-c day0c` | Rebuilds the golden reference and checks it against the hash / size / magic / entry address recorded in the spec |

> [!IMPORTANT]
> The artifact gate is a **local** gate: GitHub's stock runners have no VEXcode Pro V5.
> A CI gate that is always green is worse than no gate at all. CI therefore only offers a
> manual, self-hosted-runner entry point.
>
> The hash is **not** hardcoded in the script — it is read from the spec
> (§ 2.1), so there is never a second copy to drift.

## Pull request process

1. **One PR does one thing.** If the description needs an "and", it is probably two PRs.
2. **Run the gates.** *A gate that wasn't run is a gate that didn't pass.* Say which ones
   you ran — and which you did not.
3. **Summarize the change in the commit message**, and add a `Co-Authored-By` trailer for
   any AI assistant that contributed code.
4. **Keep the facts in sync** — see [Conventions](#conventions).

Changing the **binding surface** (`spike/day0-c/include/jhyy_vex.h`) costs more than it
looks: route A and route B both call those symbols, so a rename or a signature change is a
change to *both* routes. Say so explicitly in the PR description.

Changing the **spec's measured values** costs the artifact gate: the hash list in § 2.1 has
to be updated and `scripts/check-artifacts.sh` re-run.

## Conventions

- **Numbers that change live in [`docs/00-事实基线.md`](docs/00-%E4%BA%8B%E5%AE%9E%E5%9F%BA%E7%BA%BF.md).**
  Every other document links to them instead of repeating them; restating a number is how
  it starts drifting.
- **The acceptance line never gets ahead of the fact baseline.** Marking something
  with the "✅ 已实测" (measured) marker requires the corresponding section in the fact
  baseline to exist *and* to have content. The docs gate enforces this.
- **Both READMEs change together** (`README.md` and `README.zh-CN.md`) — a facade that has
  forked is worse than one that is out of date.
- **Docs-only changes still have to be fact-checked**: does the limitation still exist?
  Has the thing that fixed it shipped? A wrong document is worse than a stale one.
- **Prose in the Chinese-language documents uses Simplified Chinese only.** The
  repository-level documents (README, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT) are in
  English, matching the rest of the family; `docs/` and the Chinese README are in Chinese.
- **Artifacts are never committed.** They contain the official SDK's `libv5rt.a`, which is
  VEX-proprietary — see [`SECURITY.md`](SECURITY.md).

## License

Source: **MIT** — see [`LICENSE`](LICENSE).

The **artifacts** are a separate question: they link the official VEX SDK's `libv5rt.a` and
are therefore subject to VEX's redistribution EULA. Do not publish them before that is
settled — see [`SECURITY.md`](SECURITY.md).
