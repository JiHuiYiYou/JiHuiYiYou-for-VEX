<!--
  One PR does one thing. If the description needs an "and", it is probably two PRs.

  The full rules live in CONTRIBUTING.md — this template only asks for the parts
  that are easy to forget.
-->

### What this PR changes

<!--
  One or two sentences. What is different after this merges?
  If it adds a measured value: which section of the fact baseline changed?
-->

### Why

<!--
  The problem, not the solution. If this fixes an issue, say which one
  ("Fixes #123").
  If it adds a measurement: which "待测" (to be measured) entry does it close?
-->

### How it was verified

<!--
  Which gates you ran, and what you saw. A gate that was not run is a gate that
  did not pass — so name the ones you did not run, too.

  The full gate list is in docs/第0步-验收线.md § 6.
-->

- [ ] Docs gate (`python scripts/check-docs.py`)
- [ ] Docs-gate self-test (`python scripts/check-docs.py --self-test`)
- [ ] Shell gate (`bash -n` + `shellcheck scripts/*.sh`)
- [ ] Artifact gate (`scripts/check-artifacts.sh`) — **needs VEXcode Pro V5**; say so if you did not run it

### Notes for the reviewer

<!--
  Anything that makes review faster: the parts you are unsure about, the
  trade-offs you made, the corners you deliberately left alone.

  If you changed the binding surface (include/jhyy_vex.h) or a measured value in
  the fact baseline, say so explicitly — route A and route B both call those
  symbols, and the reviewer needs to know before merging.
-->

- [ ] This changes the **binding surface** (an `extern fn` name or signature) — route A and route B both change
- [ ] This changes a **measured value in the fact baseline** — the gate checks the hash list
- [ ] This changes only documentation / scripts / templates
