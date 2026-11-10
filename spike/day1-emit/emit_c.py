#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""emit_c.py —— `jhyy dump` 的 AST → C 源码（Day 1–2 的探针）

用法：
    python spike/day1-emit/emit_c.py <dump.txt> [--target vex|host] [-o out.c]
    python spike/day1-emit/emit_c.py --self-test

⚠️ **这个文件是探针**（验收线 § 3.1）：只吃主仓 `jhyy dump` 的**文本输出**，
**主仓一行都不用改**（永久旁路，见验收线 § 3.4）。

最小子集（验收线 § 2）：常量 · `let` · 算术 · `if`/`while` · 函数调用 ·
`extern fn` 声明 · 字符串字面量 · struct 布局。

**入口符号**：`main_jhyy` → **`main`**（VEX 的 `vexMain` 用 `R_ARM_ABS32 main`
取用户 main 的地址，事实基线 § 9.3 ⇒ 必须是**不带修饰**的 `main`）。

**指针宽度**：JHYY 语义锁 64 位，但 C 路**不受影响** —— 宽度由 clang 的
`-target thumbv7` 决定（事实基线 § 8.1 末尾）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from astdump import Node, parse  # noqa: E402


class EmitError(Exception):
    """最小子集不支持的东西 —— **记进规格书的问题清单**，不在这里绕过。"""


# ── 类型映射 ─────────────────────────────────────────────────────────────
# prim 编号来自主仓 `types.jhyy`（PRIM_I8=0 … PRIM_BOOL=10）
PRIM_TO_C = {
    0: "int8_t", 1: "int16_t", 2: "int32_t", 3: "int64_t",
    4: "uint8_t", 5: "uint16_t", 6: "uint32_t", 7: "uint64_t",
    8: "float", 9: "double", 10: "bool",
}

# JHYY 的类型名（IDENT name=...）→ C 类型
PRIM_NAME_TO_C = {
    "i8": "int8_t", "i16": "int16_t", "i32": "int32_t", "i64": "int64_t",
    "u8": "uint8_t", "u16": "uint16_t", "u32": "uint32_t", "u64": "uint64_t",
    "f32": "float", "f64": "double", "bool": "bool", "void": "void",
}

# ⚠️ **`*u8` → `char *`**（探针的简化，写在这里是为了不被当成"事实"）：
#    VEX 的 C API 与 printf 的 `%s` 都要 `char *`；
#    映成 `unsigned char *` 会给每一处调用都带一个指针类型 warning。
#    真正做绑定面时按每个 `extern fn` 的 C 侧签名逐个定（事实基线 § 9.2）。

# 64 位类型（算术提升用）
WIDE = {"int64_t", "uint64_t", "double"}

ENTRY_NAME = "main_jhyy"
C_ENTRY = "main"


class Emitter:
    def __init__(self, target: str = "host", extern_decls: str = "auto"):
        self.target = target
        # extern fn 原型要不要发：
        #   vex  → **发**（v5.h 里已有真声明 ⇒ 类型对不上就是 C 编译错误
        #                  ⇒ 正好当**绑定面 ABI 的检查器**）
        #   host → **不发**（printf 这些由 libc 的头文件拥有 ⇒ 重复声明会
        #                  "conflicting types" 报错）
        if extern_decls == "auto":
            extern_decls = "emit" if target == "vex" else "omit"
        self.extern_decls = extern_decls
        self.func_ret: dict[str, str] = {}      # 函数名 → C 返回类型
        self.func_params: dict[str, list[tuple[str, str]]] = {}
        self.struct_fields: dict[str, list[tuple[str, str]]] = {}
        self.var_types: dict[str, str] = {}

    # ── 类型位置 ────────────────────────────────────────────────────────
    def c_type(self, node: Node) -> str:
        """类型节点 → C 类型字符串。"""
        k = node.kind
        if k == "IDENT":
            name = node.get("name") or ""
            return PRIM_NAME_TO_C.get(name, name)   # 未知名字 = struct 别名
        if k == "UNARY" and node.get("op") == "*":
            inner = self.c_type(node.children[0])
            return "char *" if inner == "uint8_t" else inner + " *"
        raise EmitError(f"类型位置不支持 {k}")

    # ── 类型推导（`let` 不写类型时用） ──────────────────────────────────
    def infer_type(self, node: Node) -> str:
        k = node.kind
        if k == "INT":
            prim = int(node.get("prim") or "2")
            return PRIM_TO_C.get(prim, "int32_t")
        if k == "STRING":
            return "uint8_t *"
        if k == "STRUCT_LIT":
            return node.get("type") or "int"
        if k == "CALL":
            name = node.children[0].get("name") or ""
            if name not in self.func_ret:
                raise EmitError(f"调用了没见过的函数 {name}（推导不出返回类型）")
            return self.func_ret[name]
        if k == "IDENT":
            name = node.get("name") or ""
            return self.var_types.get(name, "int32_t")
        if k == "FIELD":
            obj = node.children[0]          # 基对象（IDENT 带 field= 属性）
            oname = obj.get("name") or ""
            fld = obj.get("field") or ""
            ctype = self.var_types.get(oname)
            if ctype is None or ctype not in self.struct_fields:
                raise EmitError(f"推不出 {oname}.{fld} 的类型")
            for fname, ftype in self.struct_fields[ctype]:
                if fname == fld:
                    return ftype
            raise EmitError(f"{ctype} 没有字段 {fld}")
        if k == "BINARY":
            op = node.get("op") or ""
            lt = self.infer_type(node.children[0])
            rt = self.infer_type(node.children[1])
            if op in ("<", ">", "<=", ">=", "==", "!="):
                return "bool"
            return rt if (lt not in WIDE and rt in WIDE) else lt
        if k == "UNARY":
            return self.infer_type(node.children[0])
        if k == "CAST":
            return self.c_type(node.children[1])
        raise EmitError(f"推不出 {k} 的类型")

    # ── 表达式位置 ──────────────────────────────────────────────────────
    def expr(self, node: Node) -> str:
        k = node.kind
        if k == "IDENT":
            name = node.get("name") or ""
            # ⚠️ 字段访问：基对象是 IDENT，但带 `field=` 属性（`a field=x`）
            fld = node.get("field")
            return f"{name}.{fld}" if fld else name
        if k == "INT":
            return node.get("value") or "0"
        if k == "STRING":
            # AST 里 chars 已经是带引号的 C 字符串字面量（源文本转义与 C 相同）
            return node.get("chars") or '""'
        if k == "BINARY":
            op = node.get("op") or "+"
            return f"({self.expr(node.children[0])} {op} {self.expr(node.children[1])})"
        if k == "UNARY":
            op = node.get("op") or "-"
            return f"({op}{self.expr(node.children[0])})"
        if k == "CAST":
            return f"(({self.c_type(node.children[1])}){self.expr(node.children[0])})"
        if k == "CALL":
            name = node.children[0].get("name") or ""
            args = ", ".join(self.expr(a) for a in node.children[1:])
            return f"{name}({args})"
        if k == "FIELD":
            # 字段访问：基对象在**子节点**上（那个 IDENT 带 `field=` 属性）
            return f"({self.expr(node.children[0])})"
        if k == "STRUCT_LIT":
            ty = node.get("type") or "int"
            parts = [f".{f.get('name')} = {self.expr(f.children[0])}" for f in node.children]
            return f"(({ty}){{ {', '.join(parts)} }})"
        if k == "ASSIGN":
            return f"({self.expr(node.children[0])} = {self.expr(node.children[1])})"
        raise EmitError(f"表达式位置不支持 {k}")

    # ── 语句 ────────────────────────────────────────────────────────────
    def stmt(self, node: Node, ind: int) -> list[str]:
        pad = "    " * ind
        k = node.kind
        if k == "BLOCK":
            out = [pad + "{"]
            for c in node.children:
                out += self.stmt(c, ind + 1)
            out.append(pad + "}")
            return out
        if k == "LET":
            name = node.get("name") or "_"
            kids = node.children
            if len(kids) == 2:
                ctype = self.c_type(kids[0])
                init = self.expr(kids[1])
            elif len(kids) == 1:
                ctype = self.infer_type(kids[0])
                init = self.expr(kids[0])
            else:
                raise EmitError("LET 的子节点个数不对")
            self.var_types[name] = ctype
            return [f"{pad}{ctype} {name} = {init};"]
        if k == "EXPR_STMT":
            return [f"{pad}{self.expr(node.children[0])};"]
        if k == "RETURN":
            if not node.children:
                return [f"{pad}return;"]
            return [f"{pad}return {self.expr(node.children[0])};"]
        if k == "ASSIGN":
            return [f"{pad}{self.expr(node.children[0])} = {self.expr(node.children[1])};"]
        if k == "IF":
            cond = self.expr(node.children[0])
            out = [f"{pad}if ({cond}) {{"]
            out += self.body(node.children[1:], ind + 1)
            out.append(pad + "}")
            return out
        if k == "WHILE":
            cond = self.expr(node.children[0])
            out = [f"{pad}while ({cond}) {{"]
            out += self.body(node.children[1:], ind + 1)
            out.append(pad + "}")
            return out
        raise EmitError(f"语句位置不支持 {k}")

    def body(self, kids: list[Node], ind: int) -> list[str]:
        """if / while 的身体：BLOCK 节点**只出它的语句**（不要多一层花括号）。"""
        out: list[str] = []
        for c in kids:
            if c.kind == "BLOCK":
                for s in c.children:
                    out += self.stmt(s, ind)
            else:
                out += self.stmt(c, ind)
        return out

    # ── 声明 ────────────────────────────────────────────────────────────
    def collect(self, root: Node) -> None:
        """先扫一遍：函数签名 + struct 字段（`let` 的类型推导要用）。"""
        for decl in root.children:
            if decl.kind == "FUNC_DECL":
                name = decl.get("name") or ""
                ret = decl.kid("RET")
                self.func_ret[name] = self.c_type(ret.children[0]) if ret and ret.children else "void"
                params = []
                for p in decl.kids("PARAM"):
                    params.append((p.get("name") or "", self.c_type(p.children[0])))
                self.func_params[name] = params
            elif decl.kind == "TYPE_DECL":
                name = decl.get("name") or ""
                sd = decl.kid("STRUCT_DEF")
                fields = []
                if sd:
                    for f in sd.kids("FIELD"):
                        fields.append((f.get("name") or "", self.c_type(f.children[0])))
                self.struct_fields[name] = fields

    def decl(self, node: Node) -> list[str]:
        k = node.kind
        if k == "TYPE_DECL":
            name = node.get("name") or ""
            sd = node.kid("STRUCT_DEF")
            out = ["typedef struct {"]
            if sd:
                for f in sd.kids("FIELD"):
                    out.append(f"    {self.c_type(f.children[0])} {f.get('name')};")
            out.append(f"}} {name};")
            return out
        if k == "FUNC_DECL":
            name = node.get("name") or ""
            cname = C_ENTRY if name == ENTRY_NAME else name
            ret = node.kid("RET")
            rtype = self.c_type(ret.children[0]) if ret and ret.children else "void"
            if name == ENTRY_NAME:
                # ⚠️ C 的入口返回类型必须**字面**是 `int` ——
                #    clang 会警告 "return type of 'main' is not 'int'"（-Wmain-return-type）。
                rtype = "int"
            params = ", ".join(
                (f"{t}{n}" if t.endswith("*") else f"{t} {n}")
                for n, t in self.func_params.get(name, [])
            ) or "void"
            proto = f"{rtype} {cname}({params})"
            if node.get("extern") == "1":
                if self.extern_decls == "omit":
                    return []
                return [f"extern {proto};"]
            out = [proto + " {"]
            body = node.kid("BLOCK")
            if body:
                for c in body.children:
                    out += self.stmt(c, 1)
            out.append("}")
            return out
        raise EmitError(f"声明位置不支持 {k}")

    # ── 整个文件 ────────────────────────────────────────────────────────
    def emit(self, root: Node) -> str:
        self.collect(root)
        head = [
            "/* 由 spike/day1-emit/emit_c.py 从 `jhyy dump` 的 AST 生成 —— 不要手改。",
            " * 探针，不是产品（验收线 § 3.1）。",
            " */",
        ]
        if self.target == "vex":
            head += [
                '#include "v5.h"',
                "#include <stdint.h>",
                "#include <stdbool.h>",
            ]
        else:
            head += [
                "#include <stdint.h>",
                "#include <stdbool.h>",
                "#include <stdio.h>",
                "#include <stdlib.h>",
            ]
        body: list[str] = []
        for d in root.children:
            if d.kind in ("FUNC_DECL", "TYPE_DECL"):
                body += self.decl(d)
            elif d.kind == "IMPORT":
                continue
            else:
                raise EmitError(f"模块级不支持 {d.kind}")
        return "\n".join(head + [""] + body) + "\n"


# ── 自测 ────────────────────────────────────────────────────────────────
SELF_TEST_SRC = """MODULE @t.jhyy:1:1 no_std=0 ndecls=3
  FUNC_DECL @t.jhyy:1:8 name=printf nparams=1 extern=1 inline=0 naked=0
    PARAM name=fmt
      UNARY @t.jhyy:1:24 op=*
        IDENT @t.jhyy:1:24 name=u8
    RET
      IDENT @t.jhyy:1:39 name=i32
  TYPE_DECL @t.jhyy:2:1 name=P ntype_params=0
    STRUCT_DEF @t.jhyy:2:10 nfields=2
      FIELD name=x
        IDENT @t.jhyy:2:22 name=i32
      FIELD name=y
        IDENT @t.jhyy:2:30 name=i32
  FUNC_DECL @t.jhyy:4:1 name=main_jhyy nparams=0 extern=0 inline=0 naked=0
    RET
      IDENT @t.jhyy:4:19 name=i32
    BLOCK @t.jhyy:4:1 nstmts=3
      LET @t.jhyy:5:5 mut=1 name=i
        IDENT @t.jhyy:5:16 name=i32
        INT @t.jhyy:5:22 value=0 prim=2
      LET @t.jhyy:6:5 mut=0 name=a
        STRUCT_LIT @t.jhyy:6:13 type=P nfields=2
          FIELD name=x
            INT @t.jhyy:6:20 value=1 prim=2
          FIELD name=y
            INT @t.jhyy:6:26 value=2 prim=2
      WHILE @t.jhyy:7:5
        BINARY @t.jhyy:7:11 op=<
          IDENT @t.jhyy:7:11 name=i
          INT @t.jhyy:7:15 value=3 prim=2
        BLOCK @t.jhyy:7:5 nstmts=1
          EXPR_STMT @t.jhyy:8:9
            ASSIGN @t.jhyy:8:9
              IDENT @t.jhyy:8:9 name=i
              BINARY @t.jhyy:8:13 op=+
                IDENT @t.jhyy:8:13 name=i
                INT @t.jhyy:8:17 value=1 prim=2
"""


def self_test() -> int:
    """证明这个 emitter **能对** —— 断言的是**期望的 C 文本**，不是 observed 反推。"""
    c = Emitter(target="host").emit(parse(SELF_TEST_SRC))

    expect = [
        "typedef struct {",                          # struct → typedef
        "    int32_t x;",
        "} P;",
        "int main(void) {",                          # main_jhyy → main（返回类型必须是字面 int）
        "    int32_t i = 0;",                        # let 带类型
        "    P a = ((P){ .x = 1, .y = 2 });",        # struct 字面量 + 推导类型
        "    while ((i < 3)) {",                     # while
        "        (i = (i + 1));",                    # 赋值
    ]
    for e in expect:
        assert e in c, f"C 里缺：{e!r}\n---- 实际 ----\n{c}"

    # ⚠️ host 目标**不**发 extern 原型（libc 头文件拥有 ⇒ 重复声明会 conflicting types）
    assert "extern int32_t printf" not in c, c

    # VEX 目标：**发** extern 原型（v5.h 里已有真声明 ⇒ 类型对不上就是 C 错误
    #            ⇒ 正好当绑定面 ABI 的检查器）
    v = Emitter(target="vex").emit(parse(SELF_TEST_SRC))
    assert '#include "v5.h"' in v, v
    assert "int main(void)" in v, v
    assert "extern int32_t printf(char *fmt);" in v, v

    print("✔ 自测通过：extern 原型（vex 发 / host 不发）/ struct / 入口改名 / "
          "let / 推导 / while / 赋值")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="jhyy dump 的 AST → C 源码")
    ap.add_argument("dump", type=Path, nargs="?", help="dump 文本文件（- 表示 stdin）")
    ap.add_argument("--target", choices=["host", "vex"], default="host")
    ap.add_argument("--extern-decls", choices=["auto", "emit", "omit"], default="auto",
                    help="extern fn 原型要不要发（auto：vex 发、host 不发）")
    ap.add_argument("-o", type=Path, help="输出文件（默认 stdout）")
    ap.add_argument("--self-test", action="store_true", help="自测")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.dump is None:
        ap.error("需要 dump 文件（或用 --self-test）")

    text = sys.stdin.read() if str(args.dump) == "-" else args.dump.read_text(encoding="utf-8")
    try:
        c = Emitter(target=args.target, extern_decls=args.extern_decls).emit(parse(text))
    except EmitError as e:
        print(f"emitter 不支持：{e}", file=sys.stderr)
        return 2

    if args.o:
        args.o.write_text(c, encoding="utf-8", newline="\n")
        print(f"✔ 已写入 {args.o}")
    else:
        print(c)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
