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
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "binding"))
from astdump import Node, parse  # noqa: E402
import binding_surface  # noqa: E402


class EmitError(Exception):
    """最小子集不支持的东西 —— **记进规格书的问题清单**，不在这里绕过。"""


# ⚠️ 主仓 `ast_dump.jhyy:86` 的 `ad_kv_hex64()` 有个**真 bug**：
#    `nib >= 10` 时算的是 `87 + (nib - 10)`（'W'..'[' '\'）而不是 `97 + ...`（'a'..'f'）
#    ⇒ FLOAT 的位模式被打印成怪字符（'W' 'X' 'Y' 'Z' '[' '\'）。
#    ⇒ 这里**解码回来**（不改主仓 —— 永久旁路）。
#    ★ 已登记为**主仓台账 W-227**（2026-11-14）⇒ 修法 = `87` 改 `97`（一个字符）。
_HEX_DIGIT_FALLBACK = {
    "W": "a", "X": "b", "Y": "c", "Z": "d",
    "[": "e", "\\": "f",
}


def decode_broken_hex(text: str) -> int:
    """把主仓那个坏掉的 hex 打印**还原**成 64 位整数。"""
    s = text.strip()
    if s.startswith("0x"):
        s = s[2:]
    fixed = "".join(_HEX_DIGIT_FALLBACK.get(ch, ch) for ch in s)
    try:
        return int(fixed, 16)
    except ValueError as e:
        raise EmitError(f"看不懂的 hex 位模式 {text!r}（{e}）") from e


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


_ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "0": "\0",
    "b": "\b", "f": "\f", "v": "\v", "a": "\a",
}


def decode_dump_string(dumped: str) -> str:
    """AST dump 里 `chars=` 的内容 → 字符串的**值**。

    ★ **dump 对字符串是无损的**（实测 2026-11-14 复核）：
    主仓 parser 把字符串字面量的**转义文本原样**存进 AST（`ast_new_string`
    存的是 token 里的文本，`len` 也是文本长度）⇒ dump 打印 `(*ds).chars`
    ⇒ **逐字等于源码里的转义文本**（实测：`"b\\b\\n"` ⇒ dump 里也是 `"b\\b\\n"`）。

    ⇒ 这里把 dump 文本**解码成值**，再由 `c_string_literal()` 按 C 重编码。

    ⚠️ **曾经误判过一次**（2026-11-10，本仓记成"dump 有损 ⇒ 含反斜杠不可靠"）：
    起因是**测试文件自己**是用 shell heredoc 写的 ⇒ 反斜杠被吃掉了一个
    （WORKING-RULES：「含反斜杠的批量改写不要走 bash heredoc」）
    ⇒ 看着像"dump 压掉了反斜杠"，其实**源文件本来就少一个**。
    ⇒ 2026-11-14 用 Write 工具落盘重测 ⇒ dump 与源**逐字节相同** ⇒ 撤销那个结论。
    """
    s = dumped
    if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    out: list[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1] in _ESCAPES:
            out.append(_ESCAPES[s[i + 1]])
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def c_string_literal(value: str) -> str:
    """字符串的值 → C 的字符串字面量。"""
    out = ['"']
    for ch in value:
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        elif ord(ch) < 32 or ord(ch) == 127:
            out.append(f"\\{ord(ch):03o}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


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
        if k == "ARRAY_TYPE":
            elem, size = self.array_info(node)
            return f"{elem}[{size}]"
        raise EmitError(f"类型位置不支持 {k}")

    def jhyy_type(self, node: Node) -> str:
        """类型节点 → **JHYY 侧**的类型名（`i32` / `*u8` …）。

        ⚠️ 跟 `c_type` 分开：绑定面表里记的是 **JHYY 侧**的声明
        （事实基线 § 9.2），而 C 侧的类型由表里的**精确 C 原型**决定
        （如 `V5_DeviceT` ≠ `char *`）。
        """
        k = node.kind
        if k == "IDENT":
            return node.get("name") or ""
        if k == "UNARY" and node.get("op") == "*":
            return "*" + self.jhyy_type(node.children[0])
        raise EmitError(f"类型位置不支持 {k}")

    def array_info(self, node: Node) -> tuple[str, str]:
        """ARRAY_TYPE → (元素类型, 长度表达式)。"""
        elem = self.c_type(node.children[0])
        size = self.expr(node.children[1]) if len(node.children) > 1 else ""
        return elem, size

    # ── 类型推导（`let` 不写类型时用） ──────────────────────────────────
    def infer_type(self, node: Node) -> str:
        k = node.kind
        if k == "INT":
            prim = int(node.get("prim") or "2")
            return PRIM_TO_C.get(prim, "int32_t")
        if k == "STRING":
            return "uint8_t *"
        if k == "BOOL":
            return "bool"
        if k == "FLOAT":
            return "double"
        if k == "UNARY":
            op = node.get("op") or "-"
            if op == "!":
                return "bool"
            return self.infer_type(node.children[0])
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

    def float_lit(self, node: Node) -> str:
        """FLOAT 节点 → C 的浮点字面量。

        ⚠️ 主仓的 hex 打印是坏的（见 `decode_broken_hex`）⇒ 这里还原位模式，
        再用 Python 的 repr（**最短往返表示**）出十进制 ⇒ C 的 strtod 解析回来
        一定是同一个位模式 ✓
        """
        prim = int(node.get("prim") or "9")
        if prim != 9:
            raise EmitError("f32 的位模式在 AST dump 里取不回来"
                            "（dump 固定读 8 字节当 i64）⇒ 只支持 f64")
        bits = decode_broken_hex(node.get("bits") or "0")
        val = struct.unpack(">d", bits.to_bytes(8, "big"))[0]
        return repr(val)

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
        if k == "BOOL":
            # ⚠️ dump 里 `value=true` / `value=false`（**不是** 1/0）
            return "true" if (node.get("value") or "") == "true" else "false"
        if k == "STRING":
            # AST 的 chars 是**转义过的文本**，且 dump 有损（见 decode_dump_string）
            return c_string_literal(decode_dump_string(node.get("chars") or '""'))
        if k == "FLOAT":
            return self.float_lit(node)
        if k == "UNARY":
            # 表达式位置的一元运算（类型位置的 `*` 走 c_type）
            # ⚠️ C emitter 的 expr() 返回的是**字符串**
            op = node.get("op") or "-"
            inner = self.expr(node.children[0])
            if op == "-":
                return f"(-({inner}))"
            if op == "!":
                return f"(!({inner}))"
            if op == "~":
                return f"(~({inner}))"
            if op == "*":
                return f"(*({inner}))"
            raise EmitError(f"暂不支持的一元运算 {op}")
        if k == "BINARY":
            op = node.get("op") or "+"
            return f"({self.expr(node.children[0])} {op} {self.expr(node.children[1])})"
        if k == "UNARY":
            op = node.get("op") or "-"
            return f"({op}{self.expr(node.children[0])})"
        if k == "CAST":
            # ⚠️ 类型**不能丢**：`200 as u8` 在 C 里写成 `200` 会溢出成别的值
            tgt = self.c_type(node.children[1])
            return f"(({tgt}){self.expr(node.children[0])})"
        if k == "CALL":
            name = node.children[0].get("name") or ""
            args = ", ".join(self.expr(a) for a in node.children[1:])
            return f"{name}({args})"
        if k == "ARRAY_LIT":
            # C 里没有"数组字面量"这个表达式 ⇒ 用初始化器的花括号（只在初始化位置合法）
            items = ", ".join(self.expr(e) for e in node.children)
            return "{" + items + "}"
        if k == "INDEX":
            return f"({self.expr(node.children[0])}[{self.expr(node.children[1])}])"
        if k == "SLICE_RANGE":
            # ⚠️ C 里没有切片 ⇒ 只给指针，**长度丢了** ⇒ 不能悄悄发出去
            raise EmitError("SLICE_RANGE（切片）暂不支持：长度信息会丢，"
                            "按验收线 § 3.1 记进问题清单，不在这里绕过")
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
                tnode, init_node = kids
                if tnode.kind == "ARRAY_TYPE":
                    # ⚠️ C 的数组声明：名字要**插在**类型和长度之间
                    #    （`int32_t arr[3]`，不是 `int32_t[3] arr`）
                    elem, size = self.array_info(tnode)
                    self.var_types[name] = f"{elem}[]"
                    return [f"{pad}{elem} {name}[{size}] = {self.expr(init_node)};"]
                ctype = self.c_type(tnode)
                init = self.expr(init_node)
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
            cond = self.cond_text(node.children[0])
            blocks = node.children[1:]
            out = [f"{pad}if ({cond}) {{"]
            out += self.body(blocks[:1], ind + 1)
            out.append(pad + "}")
            if len(blocks) > 1:
                # 第二个 BLOCK = else 分支
                out.append(pad + "else {")
                out += self.body(blocks[1:2], ind + 1)
                out.append(pad + "}")
            return out
        if k == "WHILE":
            cond = self.cond_text(node.children[0])
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

    def cond_text(self, node: Node) -> str:
        """if / while 的**条件**文本。

        ⚠️ **顶层的 `==` / `!=` 少包一层括号** ——
        clang 的 `-Wparentheses-equality`（`-Wall` 里有）会对
        `if ((a == b))` 报 "equality comparison with extraneous parentheses"
        ⇒ VEX 构建（`-Wall`）会**每次都告警** ⇒ 这里去掉那层多余的括号。
        （只有顶层是相等比较时才去；`||` / `&&` 的顶层不受影响。）
        """
        s = self.expr(node)
        if node.kind == "BINARY" and (node.get("op") or "") in ("==", "!="):
            return s[1:-1]
        return s

    # ── 声明 ────────────────────────────────────────────────────────────
    def check_binding(self, decl: Node) -> binding_surface.Binding:
        """VEX 目标：`extern fn` 必须在**绑定面表**里，且 JHYY 声明要与表一致。

        ⇒ 绑定面表是唯一真相源；表里没有 ⇒ 直接报错（不猜、不悄悄发出去）。
        ⇒ JHYY 侧声明与表不一致 ⇒ 报错（说明源码或表漂移了）。
        """
        name = decl.get("name") or ""
        b = binding_surface.lookup(name)
        if b is None:
            raise EmitError(
                f"extern fn {name} 不在绑定面表里"
                f"（spike/binding/binding_surface.py）\n"
                f"    ⇒ 先把它的 JHYY 声明 / 精确 C 原型 / ABI 写进表里，再来用"
            )
        ret = decl.kid("RET")
        jret = self.jhyy_type(ret.children[0]) if ret and ret.children else ""
        got = tuple((p.get("name") or "", self.jhyy_type(p.children[0]))
                    for p in decl.kids("PARAM"))
        if jret != b.jhyy_ret or got != b.jhyy_params:
            fmt = lambda ps: ", ".join(f"{n}: {t}" for n, t in ps)  # noqa: E731
            raise EmitError(
                f"extern fn {name} 的 JHYY 声明与绑定面表不一致\n"
                f"    源码：({fmt(got)}) -> {jret or 'void'}\n"
                f"    表里：({fmt(b.jhyy_params)}) -> {b.jhyy_ret or 'void'}"
            )
        return b

    def collect(self, root: Node) -> None:
        """先扫一遍：函数签名 + struct 字段（`let` 的类型推导要用）。"""
        for decl in root.children:
            if decl.kind == "FUNC_DECL":
                name = decl.get("name") or ""
                ret = decl.kid("RET")
                params = []
                for p in decl.kids("PARAM"):
                    params.append((p.get("name") or "", self.c_type(p.children[0])))
                self.func_params[name] = params
                if decl.get("extern") == "1" and self.target == "vex":
                    # ⚠️ VEX 目标：**绑定面表说了算** ——
                    #    C 侧的类型是表里的**精确 C 原型**（如 `V5_DeviceT`），
                    #    不是 JHYY 侧那个 `*u8` ⇒ 否则 clang 会报 conflicting types。
                    b = self.check_binding(decl)
                    self.func_ret[name] = b.c_ret
                else:
                    self.func_ret[name] = (self.c_type(ret.children[0])
                                           if ret and ret.children else "void")
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
                if self.target == "vex":
                    # ★ VEX 目标：**逐字**发绑定面表里的精确 C 原型
                    #   ⇒ v5.h / jhyy_vex.h 会校验它 ⇒ **C 编译器就是 ABI 检查器**
                    b = binding_surface.lookup(name)
                    if b is None:
                        raise EmitError(f"extern fn {name} 不在绑定面表里")
                    return [f"extern {b.c_proto}"]
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
                # ★ 绑定面头文件 ⇒ 生成的原型会被它**逐字校验**
                #   （`jhyy_vex_display_puts` 的 `const char *` 与表里一致）
                '#include "jhyy_vex.h"',
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


SELF_TEST_SRC2 = """MODULE @t2.jhyy:1:1 no_std=0 ndecls=1
  FUNC_DECL @t2.jhyy:1:1 name=main_jhyy nparams=0 extern=0 inline=0 naked=0
    RET
      IDENT @t2.jhyy:1:19 name=i32
    BLOCK @t2.jhyy:1:1 nstmts=3
      LET @t2.jhyy:2:5 mut=0 name=arr
        ARRAY_TYPE @t2.jhyy:2:18
          IDENT @t2.jhyy:2:19 name=i32
          INT @t2.jhyy:2:18 value=3 prim=2
        ARRAY_LIT @t2.jhyy:2:29 nelems=3
          INT @t2.jhyy:2:30 value=1 prim=2
          INT @t2.jhyy:2:33 value=2 prim=2
          INT @t2.jhyy:2:36 value=3 prim=2
      IF @t2.jhyy:3:5
        IDENT @t2.jhyy:3:8 name=arr
        BLOCK @t2.jhyy:3:5 nstmts=1
          EXPR_STMT @t2.jhyy:4:9
            ASSIGN @t2.jhyy:4:9
              INDEX @t2.jhyy:4:9
                IDENT @t2.jhyy:4:9 name=arr
                INT @t2.jhyy:4:13 value=0 prim=2
              INT @t2.jhyy:4:18 value=9 prim=2
        BLOCK @t2.jhyy:3:5 nstmts=1
          EXPR_STMT @t2.jhyy:5:9
            ASSIGN @t2.jhyy:5:9
              INDEX @t2.jhyy:5:9
                IDENT @t2.jhyy:5:9 name=arr
                INT @t2.jhyy:5:13 value=1 prim=2
              INT @t2.jhyy:5:18 value=8 prim=2
"""


SELF_TEST_SRC3 = """MODULE @t3.jhyy:1:1 no_std=0 ndecls=1
  FUNC_DECL @t3.jhyy:1:1 name=main_jhyy nparams=0 extern=0 inline=0 naked=0
    RET
      IDENT @t3.jhyy:1:19 name=i32
    BLOCK @t3.jhyy:1:1 nstmts=4
      LET @t3.jhyy:2:5 mut=0 name=a
        IDENT @t3.jhyy:2:16 name=i32
        INT @t3.jhyy:2:22 value=5 prim=2
      LET @t3.jhyy:3:5 mut=0 name=b
        UNARY @t3.jhyy:3:16 op=-
          IDENT @t3.jhyy:3:17 name=a
      LET @t3.jhyy:4:5 mut=0 name=c
        FLOAT @t3.jhyy:4:16 bits=0x3\\\\8000000000000 prim=9
      LET @t3.jhyy:5:5 mut=0 name=s
        CAST @t3.jhyy:5:15
          STRING @t3.jhyy:5:15 chars="hi\\n" len=4
          UNARY @t3.jhyy:5:26 op=*
            IDENT @t3.jhyy:5:26 name=u8
"""


# VEX 目标的自测源：`extern fn` **全部来自绑定面表**
SELF_TEST_SRC_VEX = """MODULE @tv.jhyy:1:1 no_std=0 ndecls=2
  FUNC_DECL @tv.jhyy:1:1 name=jhyy_vex_display_puts nparams=3 extern=1 inline=0 naked=0
    PARAM name=xpos
      IDENT @tv.jhyy:1:1 name=i32
    PARAM name=ypos
      IDENT @tv.jhyy:1:1 name=i32
    PARAM name=text
      UNARY @tv.jhyy:1:1 op=*
        IDENT @tv.jhyy:1:1 name=u8
    RET
  FUNC_DECL @tv.jhyy:2:1 name=main_jhyy nparams=0 extern=0 inline=0 naked=0
    RET
      IDENT @tv.jhyy:2:19 name=i32
    BLOCK @tv.jhyy:2:1 nstmts=1
      EXPR_STMT @tv.jhyy:3:5
        CALL @tv.jhyy:3:5
          IDENT @tv.jhyy:3:5 name=jhyy_vex_display_puts
          INT @tv.jhyy:3:5 value=1 prim=2
          INT @tv.jhyy:3:5 value=1 prim=2
          STRING @tv.jhyy:3:5 chars="hi" len=2
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

    # VEX 目标：**逐字**发绑定面表里的精确 C 原型
    #   ⇒ v5.h / jhyy_vex.h 会校验它 ⇒ C 编译器就是绑定面 ABI 的检查器
    v = Emitter(target="vex").emit(parse(SELF_TEST_SRC_VEX))
    assert '#include "v5.h"' in v, v
    assert '#include "jhyy_vex.h"' in v, v
    assert "int main(void)" in v, v
    assert ("extern void jhyy_vex_display_puts(int32_t xpos, int32_t ypos, "
            "const char *text);") in v, v

    # ★ VEX 目标：`extern fn` 不在绑定面表里 ⇒ **报错**（不猜、不悄悄发出去）
    try:
        Emitter(target="vex").emit(parse(
            SELF_TEST_SRC_VEX.replace("name=jhyy_vex_display_puts",
                                      "name=vexDeviceNotInTheTable")))
    except EmitError as e:
        assert "不在绑定面表里" in str(e), e
    else:
        raise AssertionError("绑定面表里没有的 extern fn 应该报错")

    # ★ VEX 目标：JHYY 声明与表不一致 ⇒ **报错**（源码或表漂移了）
    try:
        Emitter(target="vex").emit(parse(
            SELF_TEST_SRC_VEX.replace("name=u8\n", "name=u16\n")))
    except EmitError as e:
        assert "与绑定面表不一致" in str(e), e
    else:
        raise AssertionError("JHYY 声明与绑定面表不一致时应该报错")

    # 数组 / 索引 / else
    c2 = Emitter(target="host").emit(parse(SELF_TEST_SRC2))
    expect2 = [
        "int32_t arr[3] = {1, 2, 3};",   # 数组声明：名字插在类型与长度之间
        "    if (arr) {",                 # if 条件
        "    }",                          # then 块收尾
        "    else {",                     # else 分支
        "((arr[0]) = 9)",                # 索引 + 赋值
        "((arr[1]) = 8)",                # else 里的索引 + 赋值
    ]
    for e in expect2:
        assert e in c2, f"C 里缺：{e!r}\n---- 实际 ----\n{c2}"

    # 切片**不支持**（长度会丢 ⇒ 不能悄悄发出去）
    try:
        Emitter(target="host").emit(parse(
            "MODULE @s:1:1 no_std=0 ndecls=1\n"
            "  FUNC_DECL @s:1:1 name=main_jhyy nparams=0 extern=0 inline=0 naked=0\n"
            "    BLOCK @s:1:1 nstmts=1\n"
            "      LET @s:2:5 mut=0 name=sl\n"
            "        SLICE_RANGE @s:2:14\n"
            "          IDENT @s:2:14 name=arr\n"
            "          INT @s:2:18 value=0 prim=2\n"
            "          INT @s:2:21 value=2 prim=2\n"))
    except EmitError:
        pass
    else:
        raise AssertionError("切片应该报错（长度会丢），却悄悄发出来了")

    # ⚠️ 顶层 `==` / `!=` 的条件**少一层括号**
    #    （clang 的 -Wparentheses-equality 会对 `if ((a == b))` 告警 ⇒ VEX 构建会一直告警）
    c3 = Emitter(target="host").emit(parse(
        "MODULE @q.jhyy:1:1 no_std=0 ndecls=1\n"
        "  FUNC_DECL @q.jhyy:1:1 name=main_jhyy nparams=0 extern=0 inline=0 naked=0\n"
        "    BLOCK @q.jhyy:1:1 nstmts=1\n"
        "      IF @q.jhyy:2:5\n"
        "        BINARY @q.jhyy:2:8 op===\n"
        "          IDENT @q.jhyy:2:8 name=a\n"
        "          IDENT @q.jhyy:2:10 name=b\n"
        "        BLOCK @q.jhyy:2:5 nstmts=1\n"
        "          EXPR_STMT @q.jhyy:3:9\n"
        "            ASSIGN @q.jhyy:3:9\n"
        "              IDENT @q.jhyy:3:9 name=a\n"
        "              INT @q.jhyy:3:13 value=1 prim=2\n"))
    assert "if (a == b) {" in c3, c3
    assert "if ((a == b))" not in c3, c3

    print("✔ 自测通过：extern 原型（vex 发 / host 不发）/ struct / 入口改名 / "
          "let / 推导 / while / 赋值 / 数组 / 索引 / else / 切片报错 / "
          "条件不多包括号")
    return 0


def self_test_types() -> int:
    """一元运算 / 浮点（坏 hex 解码）/ 字符串转义（dump 有损 ⇒ 解码再重编码）。"""
    c = Emitter(target="host").emit(parse(SELF_TEST_SRC3))

    expect = [
        "(-(a))",                       # 一元负号
        "double c = 1.5;",              # FLOAT：坏掉的 hex 还原出来的值
        '"hi\\n"',                      # 字符串：解码成值再按 C 重编码
        "char * s = ((char *)\"hi\\n\");",
    ]
    for e in expect:
        assert e in c, f"C 里缺：{e!r}\n---- 实际 ----\n{c}"

    # 坏 hex 的还原：'W'..'^' ⇒ 'a'..'f'
    assert decode_broken_hex("0x3\\\\8000000000000") == 0x3FF8000000000000, \
        hex(decode_broken_hex("0x3\\\\8000000000000"))

    # 字符串：dump **原样**带转义 ⇒ 解码器按转义还原（两种形状都要对）
    # ① 单反斜杠 + 'b' ⇒ 退格（值 = b + BS + 换行）
    val = decode_dump_string('"b\\b\\n"')
    assert val == "b\x08\n", repr(val)
    # ② **双**反斜杠 ⇒ 真的一个反斜杠（值 = b + \ + b + 换行）
    #    ⚠️ 这一支曾经被误判成"含反斜杠的字符串不可靠"（2026-11-10）——
    #    起因是**测试文件**用 shell heredoc 写 ⇒ 反斜杠被吃掉一个 ⇒ 断言的前提就错了。
    val2 = decode_dump_string('"b\\\\b\\n"')
    assert val2 == "b\\b\n", repr(val2)

    print("✔ 自测通过：一元运算 / 浮点（坏 hex 解码）/ 字符串（解码+重编码，含双反斜杠）")
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
        return self_test() or self_test_types()
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
