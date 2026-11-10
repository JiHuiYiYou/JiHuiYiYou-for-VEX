#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""astdump.py —— 解析 `jhyy dump` 的 AST 文本（缩进 + key=value）

用法：
    python spike/day1-emit/astdump.py <dump.txt> [--self-test]

⚠️ **这个文件是探针**（验收线 § 3.1）：它只吃主仓 `jhyy dump` 的**文本输出**，
**主仓一行都不用改**（永久旁路，见验收线 § 3.4）。

输入形状（每行一个节点，子节点缩进一级 = 两个空格）：

    MODULE @hello.jhyy:1:1 no_std=0 ndecls=2
      FUNC_DECL @hello.jhyy:1:8 name=printf nparams=2 extern=1 inline=0 naked=0
        PARAM name=fmt
          UNARY @hello.jhyy:1:24 op=*
            IDENT @hello.jhyy:1:24 name=u8

节点 = `KIND [@loc] key=value ...`；值可以是**带引号的字符串**（含空格/转义）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


class Node:
    """一个 AST 节点：kind + 属性 + 子节点。"""

    __slots__ = ("kind", "loc", "attrs", "children")

    def __init__(self, kind: str, loc: str, attrs: dict[str, str]):
        self.kind = kind
        self.loc = loc
        self.attrs = attrs
        self.children: list[Node] = []

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.attrs.get(key, default)

    def kid(self, kind: str) -> "Node | None":
        """第一个 kind 匹配的子节点。"""
        for c in self.children:
            if c.kind == kind:
                return c
        return None

    def kids(self, kind: str) -> list["Node"]:
        return [c for c in self.children if c.kind == kind]

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<{self.kind} {self.attrs} kids={len(self.children)}>"


def _split_line(line: str) -> tuple[str, str, dict[str, str]]:
    """一行 → (kind, loc, attrs)。

    ⚠️ 值可能是带引号的字符串（`chars="hi there\\n"`）⇒ 得自己扫引号，
    不能简单 split()。
    """
    s = line.strip()
    kind = ""
    i = 0
    while i < len(s) and not s[i].isspace():
        kind += s[i]
        i += 1
    rest = s[i:].strip()

    loc = ""
    if rest.startswith("@"):
        j = rest.index(" ") if " " in rest else len(rest)
        loc = rest[1:j]
        rest = rest[j:].strip()

    attrs: dict[str, str] = {}
    while rest:
        eq = rest.find("=")
        if eq < 0:
            break
        key = rest[:eq].strip()
        rest = rest[eq + 1:].lstrip()
        if rest.startswith('"'):
            # 带引号的值：找收尾的引号（跳过转义）
            k = 1
            buf = ['"']
            while k < len(rest):
                ch = rest[k]
                buf.append(ch)
                if ch == "\\" and k + 1 < len(rest):
                    buf.append(rest[k + 1])
                    k += 2
                    continue
                if ch == '"':
                    k += 1
                    break
                k += 1
            val = "".join(buf)
            rest = rest[k:].lstrip()
        else:
            k = 0
            while k < len(rest) and not rest[k].isspace():
                k += 1
            val = rest[:k]
            rest = rest[k:].lstrip()
        attrs[key] = val
    return kind, loc, attrs


def parse(text: str) -> Node:
    """AST 文本 → 树。根必须是 MODULE。"""
    root: Node | None = None
    stack: list[tuple[int, Node]] = []   # (缩进层级, 节点)

    for lineno, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2 != 0:
            raise ValueError(f"第 {lineno} 行缩进不是 2 的倍数：{raw!r}")
        level = indent // 2

        kind, loc, attrs = _split_line(raw)
        if not kind:
            continue
        node = Node(kind, loc, attrs)

        while stack and stack[-1][0] >= level:
            stack.pop()
        if not stack:
            if root is not None:
                raise ValueError(f"第 {lineno} 行：根节点之后又出现了一个根")
            root = node
        else:
            stack[-1][1].children.append(node)
        stack.append((level, node))

    if root is None:
        raise ValueError("空输入")
    if root.kind != "MODULE":
        raise ValueError(f"根节点不是 MODULE，是 {root.kind}")
    return root


def dumps(node: Node, depth: int = 0) -> str:
    """树 → 文本（往返用；自测靠它）。"""
    out = ["  " * depth + node.kind]
    for k, v in node.attrs.items():
        out.append("  " * (depth + 1) + f"{k}={v}")
    for c in node.children:
        out.append(dumps(c, depth + 1))
    return "\n".join(out)


SELF_TEST_SRC = """MODULE @t.jhyy:1:1 no_std=0 ndecls=1
  FUNC_DECL @t.jhyy:2:1 name=main_jhyy nparams=0 extern=0 inline=0 naked=0
    RET
      IDENT @t.jhyy:2:19 name=i32
    BLOCK @t.jhyy:2:1 nstmts=1
      LET @t.jhyy:3:5 mut=1 name=msg
        IDENT @t.jhyy:3:16 name=*u8
        CAST @t.jhyy:3:20
          STRING @t.jhyy:3:20 chars="hi there\\n" len=9
          UNARY @t.jhyy:3:31 op=*
            IDENT @t.jhyy:3:31 name=u8
"""


def self_test() -> int:
    """证明这个解析器**能对**（也**能报错**）。"""
    tree = parse(SELF_TEST_SRC)

    assert tree.kind == "MODULE", tree.kind
    assert tree.get("ndecls") == "1", tree.attrs
    fn = tree.kid("FUNC_DECL")
    assert fn is not None and fn.get("name") == "main_jhyy", fn
    assert fn.get("extern") == "0"

    ret = fn.kid("RET")
    assert ret is not None and ret.children[0].get("name") == "i32"

    blk = fn.kid("BLOCK")
    assert blk is not None and blk.get("nstmts") == "1"

    let = blk.children[0]
    assert let.kind == "LET" and let.get("mut") == "1" and let.get("name") == "msg"

    cast = let.children[1]
    assert cast.kind == "CAST"
    string = cast.children[0]
    assert string.kind == "STRING", string.kind
    # ⚠️ 带空格 + 转义的引号值不能被切坏
    assert string.get("chars") == '"hi there\\n"', string.get("chars")
    assert string.get("len") == "9", string.get("len")

    # 缩进不是 2 的倍数 ⇒ 必须报错（不是默默吞掉）
    try:
        parse("MODULE @a:1:1 no_std=0 ndecls=0\n   BAD indent\n")
    except ValueError:
        pass
    else:
        raise AssertionError("坏缩进没有报错")

    print("✔ 自测通过：缩进树 / 引号值 / 坏缩进报错")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="解析 jhyy dump 的 AST 文本")
    ap.add_argument("dump", type=Path, nargs="?", help="dump 文本文件（- 表示 stdin）")
    ap.add_argument("--self-test", action="store_true", help="自测")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.dump is None:
        ap.error("需要 dump 文件（或用 --self-test）")

    text = sys.stdin.read() if str(args.dump) == "-" else args.dump.read_text(encoding="utf-8")
    print(dumps(parse(text)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
