#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check-docs.py —— 文档门（CI 与本地通用，退出码即闸门）。

四道检查：

  1. **链接能落地**      —— 相对链接指向的文件存在；带 `#锚点` 的，标题也真实存在
  2. **§ 引用能落地**    —— `§ N` 指向的章节在某个文档里真实存在
  3. **验收线不超前于事实基线** —— 验收线 §1 里每条 ✅ 都得指向事实基线里
     **真实存在且有内容**的章节
     ⇒ 这条门就是为「验收线先于事实基线勾勾」设的
  4. **裸路径能落地**    —— 反引号里 `docs/…` `scripts/…` `spike/…` 形式的路径真实存在

用法：
    python scripts/check-docs.py              # 检查本仓
    python scripts/check-docs.py --self-test  # 证明这个门**能红**（注入故障，断言被抓到）
    python scripts/check-docs.py --root DIR   # 检查别的目录（自测用）

⚠️ **一个从没红过的门不是门** —— 所以有 `--self-test`：
它故意把文档弄坏，然后断言每道检查都抓到了。
CI 里两个都跑（`--self-test` 也进 CI），门本身坏掉时不会静悄悄放过。
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote

# ── 仓库里"裸路径"只认这几个前缀 ─────────────────────────────────────────
REPO_PATH_PREFIXES = ("docs/", "scripts/", "spike/", ".github/")

LINK_RE = re.compile(r"\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
SECTION_REF_RE = re.compile(r"§\s*(\d+(?:\.\d+)*)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
BACKTICK_RE = re.compile(r"`([^`\n]+)`")
FENCE_RE = re.compile(r"^\s*```")

# 外部规范引用（ABI / 语言规范）里的 § 编号不在本仓，不查。
# 判定方式：看**同一句**里有没有 ABI / 规范 —— 不是看紧邻的前缀，
# 因为「JHYY ABI v4.0.0 § 6 FFI / § 3.6 名称修饰」里两个都是外部引用。
EXTERNAL_MARKER_RE = re.compile(r"\bABI\b|规范|Spec")
SENTENCE_END_RE = re.compile(r"[。！？\n]")


# ── 文本工具 ──────────────────────────────────────────────────────────────
def strip_fenced_blocks(text: str) -> str:
    """把 ``` 围栏块整段挖掉 —— 里面的 # 不是标题。"""
    out, in_fence = [], False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return "\n".join(out)


def slugify(text: str) -> str:
    """GitHub 的锚点算法近似（够用即可）。"""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_]", "", text).strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return re.sub(r"\s+", "-", text)


def section_number(heading: str):
    """`## 3. 产物格式` → '3'；`### 9.2 绑定面` → '9.2'；`### ① 规格书` → None。"""
    m = re.match(r"(\d+(?:\.\d+)*)\.?\s+\S", heading.strip())
    return m.group(1) if m else None


class Doc:
    def __init__(self, path: Path, root: Path):
        self.path = path
        self.root = root
        self.raw = path.read_text(encoding="utf-8")
        self.text = strip_fenced_blocks(self.raw)
        self.sections: dict[str, str] = {}   # "3" → 正文
        self.anchors: set[str] = set()
        self._parse()

    def _parse(self):
        lines = self.text.splitlines()
        marks = []           # (行号, 标题, 级别)
        for i, line in enumerate(lines):
            m = HEADING_RE.match(line)
            if m:
                marks.append((i, m.group(2).strip(), len(m.group(1))))
                self.anchors.add(slugify(m.group(2)))
        for idx, (line_no, heading, _level) in enumerate(marks):
            num = section_number(heading)
            if num is None:
                continue
            # 章节正文延伸到**下一个不属于本章的编号标题**为止
            # （`## 9.` 的正文要吃掉 `### 9.1` / `9.2` / `9.3` / `9.4`）
            end = len(lines)
            for j in range(idx + 1, len(marks)):
                nxt = section_number(marks[j][1])
                if nxt is None or not (nxt == num or nxt.startswith(num + ".")):
                    end = marks[j][0]
                    break
            body = "\n".join(lines[line_no + 1:end]).strip()
            self.sections[num] = body

    def sentence_before(self, pos: int) -> str:
        """取 pos 之前**同一句**的文本（句末标点或换行处断开）。"""
        head = self.text[:pos]
        cut = max((head.rfind(ch) for ch in "。！？\n"), default=-1)
        return head[cut + 1:]


def collect_docs(root: Path) -> list[Doc]:
    """本仓所有承载文字的 markdown：根目录 *.md + docs/*.md + 各探针的 README。"""
    files = list(sorted(root.glob("*.md")))
    for pattern in ("docs/*.md", "spike/*/README.md"):
        files.extend(sorted(root.glob(pattern)))
    seen, uniq = set(), []
    for p in files:
        if not p.exists():
            continue
        key = p.resolve()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return [Doc(p, root) for p in uniq]


# ── 检查 1：链接 ──────────────────────────────────────────────────────────
def check_links(docs: list[Doc]) -> list[str]:
    problems = []
    for doc in docs:
        for raw in LINK_RE.findall(doc.raw):
            if raw.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path_part, _, anchor = raw.partition("#")
            # 中文文件名两种写法都得认：直接写 `docs/00-事实基线.md`，
            # 或 percent-encode 成 `docs/00-%E4%BA%8B...md`（官网就是这么链的）。
            path_part = unquote(path_part)
            anchor = unquote(anchor)
            target = (doc.path.parent / path_part).resolve()
            if not target.exists():
                problems.append(
                    f"{doc.path.relative_to(doc.root)}: 链接指向不存在的路径 → {raw}"
                )
                continue
            if anchor and target.suffix.lower() == ".md":
                try:
                    tgt = Doc(target, doc.root)
                except Exception:
                    continue
                if slugify(anchor) not in tgt.anchors:
                    problems.append(
                        f"{doc.path.relative_to(doc.root)}: 链接锚点不存在 → {raw}"
                    )
    return problems


# ── 检查 2：§ 引用 ────────────────────────────────────────────────────────
def check_section_refs(docs: list[Doc]) -> list[str]:
    known: set[str] = set()
    for doc in docs:
        known |= set(doc.sections)
    problems = []
    for doc in docs:
        for m in SECTION_REF_RE.finditer(doc.text):
            num = m.group(1)
            if EXTERNAL_MARKER_RE.search(doc.sentence_before(m.start())):
                continue          # 外部规范（ABI / 语言规范）的 § 编号
            if num not in known:
                ctx = doc.text[max(0, m.start() - 40):m.end() + 20].replace("\n", " ")
                problems.append(
                    f"{doc.path.relative_to(doc.root)}: § {num} 在本仓任何文档里都不存在"
                    f"（上下文：…{ctx.strip()}…）"
                )
    return problems


# ── 检查 3：验收线 ↔ 事实基线 对拍 ───────────────────────────────────────
ACCEPT_DOC = "docs/第0步-验收线.md"
BASE_DOC = "docs/00-事实基线.md"
MIN_CONTENT = 40     # 章节正文少于这个字数 ⇒ 视为"没有实质内容"


def check_acceptance_vs_baseline(docs: list[Doc], root: Path) -> list[str]:
    by_path = {d.path.resolve(): d for d in docs}
    accept = by_path.get((root / ACCEPT_DOC).resolve())
    base = by_path.get((root / BASE_DOC).resolve())
    if accept is None or base is None:
        return []      # 文件不存在时不重复报（由检查 4 报）
    problems = []
    for line in accept.text.splitlines():
        if "✅" not in line or not line.strip().startswith("|"):
            continue
        for m in SECTION_REF_RE.finditer(line):
            num = m.group(1)
            if EXTERNAL_MARKER_RE.search(line[:m.start()]):
                continue          # 外部规范的 § 编号
            if num not in base.sections:
                problems.append(
                    f"{ACCEPT_DOC}: 验收线勾了 ✅（§ {num}），"
                    f"但 {BASE_DOC} 里没有 § {num} ⇒ 验收线超前于事实基线"
                )
            elif len(base.sections[num]) < MIN_CONTENT:
                problems.append(
                    f"{ACCEPT_DOC}: 验收线勾了 ✅（§ {num}），"
                    f"但 {BASE_DOC} § {num} 正文只有 {len(base.sections[num])} 字"
                    f"（< {MIN_CONTENT}）⇒ 实测值还没写进去"
                )
    return problems


# ── 检查 4：裸路径 ────────────────────────────────────────────────────────
def _is_ignored(root: Path, rel: str) -> bool:
    """这个路径是不是**故意不进版本库**的产物？

    用 `git check-ignore` 判定 —— `.gitignore` 就是「哪些是产物」的唯一真相源，
    不在脚本里另抄一份（另抄一份 = 下一个漂移源）。
    """
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "-q", "--", rel],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def check_bare_paths(docs: list[Doc], root: Path) -> list[str]:
    problems = []
    seen = set()
    for doc in docs:
        for raw in BACKTICK_RE.findall(doc.text):
            path = unquote(raw.strip().rstrip(".,;:)"))
            if not path.startswith(REPO_PATH_PREFIXES):
                continue
            if " " in path or "*" in path or "…" in path:
                continue
            if (root / path).exists():
                continue
            if _is_ignored(root, path):
                continue      # 故意不跟踪的构建产物（.gitignore 说了算）
            key = (str(doc.path), path)
            if key in seen:
                continue
            seen.add(key)
            problems.append(
                f"{doc.path.relative_to(root)}: 裸路径不存在 → {path}"
            )
    return problems


# ── 检查 5：GitHub 的 YAML 能不能解析 ──────────────────────────────────────
# ⚠️ **GitHub 自己不会告诉你 issue 模板写坏了** —— 它只是不显示那个模板。
#    一行 `description: a: b` 就能让整份模板静默消失。
def check_github_yml(root: Path) -> tuple[list[str], bool]:
    """返回 (问题列表, 是否真的检查了)。缺 pyyaml 时不假装检查过。"""
    files = sorted(root.glob(".github/workflows/*.yml")) + \
            sorted(root.glob(".github/ISSUE_TEMPLATE/*.yml"))
    if not files:
        return [], True
    try:
        import yaml
    except ImportError:
        return [], False
    problems = []
    for f in files:
        try:
            yaml.safe_load(f.read_text(encoding="utf-8"))
        except Exception as exc:
            problems.append(f"{f.relative_to(root)}: YAML 解析失败 → {exc}")
    return problems, True


# ── 汇总 ──────────────────────────────────────────────────────────────────
def check(root: Path) -> list[str]:
    docs = collect_docs(root)
    problems = []
    problems += check_links(docs)
    problems += check_section_refs(docs)
    problems += check_acceptance_vs_baseline(docs, root)
    problems += check_bare_paths(docs, root)
    yml_problems, checked = check_github_yml(root)
    problems += yml_problems
    # 去重（同一行引用同一节会被算两次）
    seen, uniq = set(), []
    for p in problems:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


# ── 自测：证明这个门能红 ──────────────────────────────────────────────────
def self_test(root: Path) -> int:
    tmp = Path(tempfile.mkdtemp(prefix="check-docs-selftest-"))
    failures = []

    def probe(label, mutate, run):
        """注入故障 → 立刻跑门 → 还原。"""
        mutate(True)
        try:
            hits = run()
        finally:
            mutate(False)
        if not hits:
            failures.append(f"❌ 自测失败：注入「{label}」后，门**没有**报错")
        else:
            print(f"  ✔ 注入「{label}」→ 门抓到了 {len(hits)} 条")

    try:
        # 复制**整个**文档集合 —— 否则 sandbox 里会缺文件，
        # 门会把「缺文件」也报出来，自测就分不清是注入的故障还是缺件。
        for src in sorted(root.iterdir()):
            if src.is_file():
                shutil.copy2(src, tmp / src.name)
        for item in ("docs", "scripts", "spike", ".github"):
            src = root / item
            if src.is_dir():
                shutil.copytree(src, tmp / item, dirs_exist_ok=True)

        # sandbox 也要是 git 仓库 —— 门会用 `git check-ignore` 判「故意不跟踪的产物」，
        # 不 init 的话 sandbox 与真实 checkout 行为不一致（自测就失去了意义）。
        try:
            subprocess.run(["git", "init", "-q"], cwd=str(tmp),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=False)
        except (OSError, subprocess.SubprocessError):
            pass

        readme = tmp / "README.md"
        accept = tmp / ACCEPT_DOC
        base = tmp / BASE_DOC
        orig_readme = readme.read_text(encoding="utf-8")
        orig_accept = accept.read_text(encoding="utf-8") if accept.exists() else ""

        # ① 断链
        def m_link(on):
            readme.write_text(
                orig_readme + ("\n[坏链](docs/根本不存在.md)\n" if on else ""),
                encoding="utf-8",
            )
        probe("断链", m_link, lambda: check_links(collect_docs(tmp)))

        # ② § 引用指向不存在的章节
        def m_sect(on):
            accept.write_text(
                orig_accept + ("\n参见 § 99.99 这一节。\n" if on else ""),
                encoding="utf-8",
            )
        probe("悬空 § 引用", m_sect, lambda: check_section_refs(collect_docs(tmp)))

        # ③ 验收线勾了事实基线没有的章节
        def m_accept(on):
            accept.write_text(
                orig_accept
                + ("\n| 99 | 编造的一项 | ✅ 已实测（§ 98） |\n" if on else ""),
                encoding="utf-8",
            )
        probe(
            "验收线超前于事实基线",
            m_accept,
            lambda: check_acceptance_vs_baseline(collect_docs(tmp), tmp),
        )

        # ④ 验收线勾了事实基线里**空**章节（正文太短）
        def m_empty(on):
            accept.write_text(
                orig_accept
                + ("\n| 98 | 另一个编造的项 | ✅ 已实测（§ 2.1） |\n" if on else ""),
                encoding="utf-8",
            )
            base.write_text(
                base.read_text(encoding="utf-8")
                + ("\n## 2.1 空章节\n\n短\n" if on else ""),
                encoding="utf-8",
            )
        probe(
            "验收线指向事实基线的空章节",
            m_empty,
            lambda: check_acceptance_vs_baseline(collect_docs(tmp), tmp),
        )

        # ⑤ 裸路径不存在
        def m_path(on):
            readme.write_text(
                orig_readme + ("\n见 `scripts/根本没有这个.sh`\n" if on else ""),
                encoding="utf-8",
            )
        probe("裸路径不存在", m_path, lambda: check_bare_paths(collect_docs(tmp), tmp))

        # ⑥ GitHub 模板的 YAML 写坏（GitHub 自己只会静默不显示那个模板）
        tpl = tmp / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml"
        if tpl.exists():
            orig_tpl = tpl.read_text(encoding="utf-8")

            def m_yml(on):
                tpl.write_text(
                    orig_tpl + ("\n  bad: description: a: b\n" if on else ""),
                    encoding="utf-8",
                )
            probe("GitHub 模板 YAML 写坏", m_yml, lambda: check_github_yml(tmp)[0])

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        for f in failures:
            print(f, file=sys.stderr)
        return 1
    print("✔ 自测通过：每道门都能红。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="文档门")
    ap.add_argument("--root", default=None, help="仓库根目录（默认脚本的上上级）")
    ap.add_argument("--self-test", action="store_true", help="证明门能红")
    args = ap.parse_args()

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent

    if args.self_test:
        print("── 文档门自测（注入故障，断言被抓）────────────")
        return self_test(root)

    problems = check(root)
    _, yml_checked = check_github_yml(root)
    if problems:
        print("❌ 文档门未通过：", file=sys.stderr)
        for p in problems:
            print(f"   • {p}", file=sys.stderr)
        return 1
    print("✔ 文档门通过：链接 / § 引用 / 验收线↔事实基线 / 裸路径")
    if yml_checked:
        print("✔ GitHub YAML 模板可解析")
    else:
        print("⚠ 跳过了 GitHub YAML 检查（缺 pyyaml）—— 用 "
              "C:\\Users\\liuzhen\\miniconda3\\python.exe 跑，或 CI 里 pip install pyyaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
