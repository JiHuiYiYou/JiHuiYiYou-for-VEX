#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""asm_emit.py —— `jhyy dump` 的 AST → **ARM 汇编**（B 路：直出机器码）

用法：
    python spike/route-b/asm_emit.py <dump.txt> [-o out.s]
    python spike/route-b/asm_emit.py --self-test

⚠️ **这个文件是探针**（验收线 § 3.1）：只吃主仓 `jhyy dump` 的文本输出，
**主仓一行都不用改**（永久旁路，验收线 § 3.4）。

★ **B 路为什么也能走"旁路"**：
   本 emitter **自己决定**寄存器和宽度 ⇒ 不经过编译器那层共享的
   `qbe_type_of()` / `size_of()`（事实基线 § 8.1 末尾、验收线 § 3.4.3）
   ⇒ **原型阶段完全不用 patch 编译器的共享层** ✔

## 目标

* 目标：VEX V5 Brain（ARMv7-A，**ARM 态**，4 字节定长指令）
* ABI：AAPCS（r0–r3 传参、r0 返回、栈 8 字节对齐）
* **整数子集**：i32 / u32 / bool / 4 字节指针
  ⇒ 不碰浮点 ⇒ **softfp 天然满足**（不产生任何 VFP 指令）
* 入口符号：`main_jhyy` → **`main`**（VEX 的 `vexMain` 用 `R_ARM_ABS32 main` 取它）

## 代码生成策略：栈机

每个表达式的结果落在 **r0**；二元运算把左操作数压栈、再算右操作数。
简单但正确 ⇒ 探针要的是**对拍一致**，不是快。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "day1-emit"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "binding"))
from astdump import Node, parse  # noqa: E402
import binding_surface  # noqa: E402

ENTRY_NAME = "main_jhyy"
C_ENTRY = "main"

# AAPCS：整数实参寄存器
ARG_REGS = ["r0", "r1", "r2", "r3"]

# JHYY 的 C 类型名 → (字节宽, 是否无符号)
CTYPE_INFO = {
    "int32_t": (4, False), "uint32_t": (4, True),
    "int16_t": (2, False), "uint16_t": (2, True),
    "int8_t": (1, False), "uint8_t": (1, True),
    "bool": (4, False),
    "char *": (4, False), "uint8_t *": (4, False),
}

# 绑定面表里 **C 返回类型** → B 路当作什么类型（宽度 + 符号性）
# ⚠️ enum 返回（V5MotorBrakeMode 等）**掩码之后**落进 4 字节槽 ⇒ 按 i32 算 ✔
RET_CTYPE = {
    "V5_DeviceT": "char *",      # 不透明指针，ARM 目标 4 字节
    "int32_t": "int32_t",
    "uint32_t": "uint32_t",
}


class AsmError(Exception):
    """B 路探针不支持的东西 —— 记进规格书的问题清单，不在这里绕过。"""


def _cond(op: str, unsigned: bool) -> str:
    """比较运算 → ARM 条件码后缀（有符号/无符号不同）。"""
    signed = {"<": "lt", ">": "gt", "<=": "le", ">=": "ge"}
    uns = {"<": "lo", ">": "hi", "<=": "ls", ">=": "hs"}
    if op in signed:
        return uns[op] if unsigned else signed[op]
    if op == "==":
        return "eq"
    if op == "!=":
        return "ne"
    raise AsmError(f"不知道的比较运算符 {op}")


class AsmEmitter:
    def __init__(self):
        self.out: list[str] = []
        self.rodata: list[str] = []
        self.strings: dict[str, str] = {}
        self.locals: dict[str, int] = {}
        self.frame = 0
        self.depth = 0          # 当前压在栈上的临时值个数（决定对齐）
        self.label_n = 0
        self.extern_names: set[str] = set()   # `extern fn` 的名字（必须都在绑定面表里）

    # ── 小工具 ─────────────────────────────────────────────────────────
    def new_label(self, tag: str) -> str:
        self.label_n += 1
        return f".L{self.label_n}_{tag}"

    def push(self) -> list[str]:
        self.depth += 1
        return ["    push {r0}"]

    def pop(self, reg: str) -> list[str]:
        self.depth -= 1
        return [f"    pop {{{reg}}}"]

    def str_lit(self, text: str) -> str:
        """字符串字面量 → .rodata 里的标签。

        ⚠️ AST 里的 `chars` **带引号**（`"hi\\n"`）⇒ 发汇编前要剥掉外层引号。
        """
        body = text
        if len(body) >= 2 and body.startswith('"') and body.endswith('"'):
            body = body[1:-1]
        if body not in self.strings:
            label = f"str{len(self.strings)}"
            self.strings[body] = label
            self.rodata.append(f'{label}:')
            self.rodata.append(f'    .ascii "{body}"')
            self.rodata.append("    .byte 0")
        return self.strings[body]

    # ── 类型 ───────────────────────────────────────────────────────────
    def c_type(self, node: Node) -> str:
        k = node.kind
        if k == "IDENT":
            name = node.get("name") or ""
            if name in ("i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64",
                        "bool", "f32", "f64"):
                return {"i8": "int8_t", "i16": "int16_t", "i32": "int32_t",
                        "i64": "int64_t", "u8": "uint8_t", "u16": "uint16_t",
                        "u32": "uint32_t", "u64": "uint64_t", "bool": "bool",
                        "f32": "float", "f64": "double"}[name]
            return name          # struct 别名
        if k == "UNARY" and node.get("op") == "*":
            inner = self.c_type(node.children[0])
            return "char *" if inner == "uint8_t" else inner + " *"
        raise AsmError(f"类型位置不支持 {k}")

    def width_unsigned(self, ctype: str) -> tuple[int, bool]:
        if ctype in ("int64_t", "uint64_t", "double"):
            raise AsmError(f"暂不支持 64 位类型（{ctype}）—— 探针只做 32 位整数子集")
        if ctype in ("float",):
            raise AsmError("暂不支持浮点（软浮点 ABI 下要额外处理 VFP）")
        if ctype in CTYPE_INFO:
            return CTYPE_INFO[ctype]
        return (4, False)          # 指针 / struct 别名：按 4 字节无符号处理

    def infer_type(self, node: Node) -> str:
        """表达式类型（够用即可：只要知道宽度与符号性）。"""
        k = node.kind
        if k == "INT":
            prim = int(node.get("prim") or "2")
            return {0: "int8_t", 1: "int16_t", 2: "int32_t", 3: "int64_t",
                    4: "uint8_t", 5: "uint16_t", 6: "uint32_t", 7: "uint64_t",
                    8: "float", 9: "double", 10: "bool"}.get(prim, "int32_t")
        if k == "STRING":
            return "char *"
        if k == "BOOL":
            return "bool"
        if k == "STRUCT_LIT":
            return node.get("type") or "int32_t"
        if k == "CALL":
            # ★ 绑定面表说了算：返回值的宽度/符号性从**精确 C 原型**推
            b = binding_surface.lookup(node.children[0].get("name") or "")
            if b is not None:
                return RET_CTYPE.get(b.c_ret, "int32_t")
            return "int32_t"        # 保守：调用结果的类型这里不细分
        if k == "IDENT":
            return self.locals.get(node.get("name") or "", "int32_t")
        if k == "BINARY":
            op = node.get("op") or ""
            lt = self.infer_type(node.children[0])
            if op in ("<", ">", "<=", ">=", "==", "!="):
                return "bool"
            rt = self.infer_type(node.children[1])
            return rt if (lt not in ("uint32_t", "uint64_t") and
                          rt in ("uint32_t", "uint64_t")) else lt
        if k == "UNARY":
            return self.infer_type(node.children[0])
        if k == "CAST":
            return self.c_type(node.children[1])
        raise AsmError(f"推不出 {k} 的类型")

    # ── 表达式（结果留在 r0） ──────────────────────────────────────────
    def expr(self, node: Node) -> list[str]:
        k = node.kind
        if k == "INT":
            v = int(node.get("value")) & 0xFFFFFFFF
            return [f"    movw r0, #{v & 0xFFFF}",
                    f"    movt r0, #{(v >> 16) & 0xFFFF}"]
        if k == "STRING":
            label = self.str_lit(node.get("chars") or '""')
            return [f"    ldr r0, ={label}"]
        if k == "BOOL":
            # ⚠️ dump 里 `value=true` / `value=false`（**不是** 1/0）
            v = 1 if (node.get("value") or "") == "true" else 0
            return [f"    movw r0, #{v}", "    movt r0, #0"]
        if k == "IDENT":
            name = node.get("name") or ""
            if name not in self.locals:
                raise AsmError(f"未声明的变量 {name}")
            return [f"    ldr r0, [sp, #{self.locals[name]}]"]
        if k == "BINARY":
            return self.binary(node)
        if k == "UNARY":
            op = node.get("op") or "-"
            inner = self.expr(node.children[0])
            if op == "-":
                return inner + ["    rsb r0, r0, #0"]
            raise AsmError(f"暂不支持的一元运算 {op}")
        if k == "CAST":
            # 32 位子集里，cast 只影响类型，不改位模式
            self.width_unsigned(self.c_type(node.children[1]))
            return self.expr(node.children[0])
        if k == "CALL":
            return self.call(node)
        if k == "ASSIGN":
            # 赋值也可以出现在表达式位置（EXPR_STMT 里）
            lhs, rhs = node.children[0], node.children[1]
            if lhs.kind != "IDENT" or (lhs.get("name") or "") not in self.locals:
                raise AsmError("暂只支持给简单变量赋值")
            off = self.locals[lhs.get("name") or ""]
            return self.expr(rhs) + [f"    str r0, [sp, #{off}]"]
        if k == "FIELD":
            raise AsmError("暂不支持字段访问（要按 struct 布局算偏移）")
        if k == "INDEX":
            raise AsmError("暂不支持数组索引")
        if k == "SLICE_RANGE":
            raise AsmError("暂不支持切片（长度会丢）")
        raise AsmError(f"表达式位置不支持 {k}")

    def binary(self, node: Node) -> list[str]:
        op = node.get("op") or "+"
        lt = self.infer_type(node.children[0])
        rt = self.infer_type(node.children[1])
        _, unsigned = self.width_unsigned(lt if lt != "bool" else rt)

        if op in ("&&", "||"):
            return self.logical(node, op)
        if op in ("<", ">", "<=", ">=", "==", "!="):
            left = self.expr(node.children[0])
            right = self.expr(node.children[1])
            cond = _cond(op, unsigned)
            out = left + self.push() + right + self.pop("r1")
            out += [f"    cmp r0, r1",
                    "    mov r0, #0",
                    f"    mov{cond} r0, #1"]
            return out

        left = self.expr(node.children[0])
        right = self.expr(node.children[1])
        out = left + self.push() + right + self.pop("r1")
        if op == "+":
            out += ["    add r0, r0, r1"]
        elif op == "-":
            out += ["    sub r0, r0, r1"]
        elif op == "*":
            out += ["    mul r0, r1, r0"]
        elif op == "/":
            out += [f"    {'udiv' if unsigned else 'sdiv'} r0, r0, r1"]
        elif op == "%":
            # ARM 没有取模 ⇒ r0 - (r0/r1)*r1
            out += ["    mov r2, r0",
                    f"    {'udiv' if unsigned else 'sdiv'} r0, r0, r1",
                    "    mul r0, r0, r1",
                    "    sub r0, r2, r0"]
        else:
            raise AsmError(f"暂不支持的二元运算 {op}")
        return out

    def logical(self, node: Node, op: str) -> list[str]:
        """短路逻辑（JHYY 的语义与 C 一样短路 —— C emitter 那条路已对拍过）。"""
        lfalse = self.new_label("false")
        ltrue = self.new_label("true")
        lend = self.new_label("end")
        out = self.expr(node.children[0])
        out += ["    cmp r0, #0"]
        if op == "&&":
            out += [f"    beq {lfalse}"]
            out += self.expr(node.children[1])
            out += ["    cmp r0, #0", f"    beq {lfalse}",
                    "    mov r0, #1", f"    b {lend}",
                    f"{lfalse}:", "    mov r0, #0", f"{lend}:"]
        else:
            out += [f"    bne {ltrue}"]
            out += self.expr(node.children[1])
            out += ["    cmp r0, #0", f"    bne {ltrue}",
                    "    mov r0, #0", f"    b {lend}",
                    f"{ltrue}:", "    mov r0, #1", f"{lend}:"]
        return out

    def call(self, node: Node) -> list[str]:
        name = node.children[0].get("name") or ""
        args = node.children[1:]
        b = binding_surface.lookup(name)
        if name in self.extern_names:
            # ★ `extern fn` 必须能在**绑定面表**里查到 ⇒ 名字、实参个数、宽度都有据
            if b is None:
                raise AsmError(
                    f"extern fn {name} 不在绑定面表里"
                    f"（spike/binding/binding_surface.py）"
                    f"⇒ 先把它的 JHYY 声明 / 精确 C 原型 / ABI 写进表里")
            if len(args) != len(b.jhyy_params):
                raise AsmError(
                    f"{name} 的实参个数不对：表里 {len(b.jhyy_params)} 个，"
                    f"调用点 {len(args)} 个")
            for _, jt in b.jhyy_params:
                w = binding_surface.jhyy_width(jt)
                # ⚠️ AAPCS：宽度 ≤ 4 字节的实参放在 r0–r3 的**低字节**，高位未定义。
                #    B 路一律传**零扩展的 32 位值**（槽位恒为 4 字节）⇒
                #    callee 按 1 字节读（bool / 短 enum）读到低字节 ✔
                #    callee 按 4 字节读（int32）读到整个字 ✔
                #    ⇒ **两种宽度都合法**，只要 ≤ 4 字节。
                if w > 4:
                    raise AsmError(
                        f"{name} 的实参类型 {jt} 是 {w} 字节 —— "
                        f"B 路只支持 ≤ 4 字节的实参")
        if len(args) > 4:
            raise AsmError(f"实参超过 4 个暂不支持（AAPCS 的栈传参还没做）：{name}")
        out: list[str] = []
        for a in args:
            out += self.expr(a) + self.push()
        # 栈上的临时值要按逆序弹回 r0..r3
        for i in range(len(args)):
            out += self.pop(ARG_REGS[len(args) - 1 - i])
        # AAPCS：调用点 sp 必须 8 字节对齐 ⇒ 临时值是奇数个时补一个
        if self.depth % 2 != 0:
            out += ["    push {r12}"]
        out += [f"    bl {name}"]
        if self.depth % 2 != 0:
            out += ["    pop {r12}"]
        if b is not None and b.ret_narrow:
            # ★ enum 返回：AAPCS 里 1 字节的返回值**只有低字节有定义**
            #   ⇒ r0 的高 3 字节是垃圾 ⇒ 必须掩码（A 路由 clang 负责）
            out += ["    and r0, r0, #0xff"]
        return out

    # ── 语句 ───────────────────────────────────────────────────────────
    def stmt(self, node: Node) -> list[str]:
        k = node.kind
        if k == "LET":
            name = node.get("name") or "_"
            kids = node.children
            if len(kids) == 2:
                ctype, init = kids[0], kids[1]
            else:
                ctype, init = None, kids[0]
            ct = self.c_type(ctype) if ctype is not None else self.infer_type(init)
            self.width_unsigned(ct)
            off = self.frame
            self.frame += 4
            self.locals[name] = off
            return self.expr(init) + [f"    str r0, [sp, #{off}]"]
        if k == "ASSIGN":
            lhs, rhs = node.children[0], node.children[1]
            if lhs.kind != "IDENT" or (lhs.get("name") or "") not in self.locals:
                raise AsmError("暂只支持给简单变量赋值")
            off = self.locals[lhs.get("name") or ""]
            return self.expr(rhs) + [f"    str r0, [sp, #{off}]"]
        if k == "EXPR_STMT":
            return self.expr(node.children[0])
        if k == "RETURN":
            if not node.children:
                return ["    mov r0, #0"]
            return self.expr(node.children[0]) + ["    ldm sp!, {r4-r11, pc}"]
        if k == "IF":
            cond = self.expr(node.children[0])
            lelse = self.new_label("else")
            lend = self.new_label("endif")
            out = cond + ["    cmp r0, #0", f"    beq {lelse}"]
            blocks = node.children[1:]
            out += self.block_body(blocks[:1])
            out += [f"    b {lend}"]
            if len(blocks) > 1:
                out += [f"{lelse}:"]
                out += self.block_body(blocks[1:2])
            out += [f"{lend}:"]
            return out
        if k == "WHILE":
            lstart = self.new_label("while")
            lend = self.new_label("endwhile")
            out = [f"{lstart}:"]
            out += self.expr(node.children[0]) + ["    cmp r0, #0", f"    beq {lend}"]
            out += self.block_body(node.children[1:])
            out += [f"    b {lstart}", f"{lend}:"]
            return out
        raise AsmError(f"语句位置不支持 {k}")

    def block_body(self, blocks: list[Node]) -> list[str]:
        out: list[str] = []
        for b in blocks:
            if b.kind == "BLOCK":
                for s in b.children:
                    out += self.stmt(s)
            else:
                out += self.stmt(b)
        return out

    # ── 函数 ───────────────────────────────────────────────────────────
    def func(self, node: Node) -> list[str]:
        name = node.get("name") or ""
        cname = C_ENTRY if name == ENTRY_NAME else name
        self.locals = {}
        self.frame = 0
        self.depth = 0

        params = node.kids("PARAM")
        body = node.kid("BLOCK")

        # 形参的栈槽先分配（body 里可能引用它们）
        param_slots: list[tuple[str, int]] = []
        for p in params:
            pname = p.get("name") or ""
            off = self.frame
            self.frame += 4
            self.locals[pname] = off
            param_slots.append((pname, off))

        # body 先发出来（局部变量在过程中才确定 ⇒ 帧大小最后才知道）
        inner: list[str] = []
        if body:
            for s in body.children:
                inner += self.stmt(s)

        frame = (self.frame + 7) // 8 * 8        # 8 字节对齐（AAPCS）
        out: list[str] = [f"    .global {cname}",
                          f"    .type {cname}, %function",
                          f"{cname}:",
                          "    push {r4-r11, lr}",
                          f"    sub sp, sp, #{frame}"]
        for i, (pname, off) in enumerate(param_slots):
            out.append(f"    str {ARG_REGS[i]}, [sp, #{off}]")
        out += inner
        out += ["    mov r0, #0",
                "    ldm sp!, {r4-r11, pc}",
                f"    .size {cname}, .-{cname}"]
        return out

    # ── 整个文件 ───────────────────────────────────────────────────────
    def jhyy_type(self, node: Node) -> str:
        """类型节点 → **JHYY 侧**的类型名（`i32` / `*u8` …）。"""
        k = node.kind
        if k == "IDENT":
            return node.get("name") or ""
        if k == "UNARY" and node.get("op") == "*":
            return "*" + self.jhyy_type(node.children[0])
        raise AsmError(f"类型位置不支持 {k}")

    def collect_externs(self, root: Node) -> None:
        """★ `extern fn` 必须**在绑定面表里**，且 JHYY 声明要与表一致。

        ⇒ B 路不猜 ABI：表里没有 ⇒ 直接报错。
        """
        for d in root.children:
            if d.kind != "FUNC_DECL" or d.get("extern") != "1":
                continue
            name = d.get("name") or ""
            self.extern_names.add(name)
            b = binding_surface.lookup(name)
            if b is None:
                raise AsmError(
                    f"extern fn {name} 不在绑定面表里"
                    f"（spike/binding/binding_surface.py）"
                    f"⇒ 先把它的 JHYY 声明 / 精确 C 原型 / ABI 写进表里")
            ret = d.kid("RET")
            jret = self.jhyy_type(ret.children[0]) if ret and ret.children else ""
            got = tuple((p.get("name") or "", self.jhyy_type(p.children[0]))
                        for p in d.kids("PARAM"))
            if jret != b.jhyy_ret or got != b.jhyy_params:
                fmt = lambda ps: ", ".join(f"{n}: {t}" for n, t in ps)  # noqa: E731
                raise AsmError(
                    f"extern fn {name} 的 JHYY 声明与绑定面表不一致\n"
                    f"    源码：({fmt(got)}) -> {jret or 'void'}\n"
                    f"    表里：({fmt(b.jhyy_params)}) -> {b.jhyy_ret or 'void'}")

    def emit(self, root: Node) -> str:
        self.collect_externs(root)
        out: list[str] = [
            "/* 由 spike/route-b/asm_emit.py 从 `jhyy dump` 的 AST 生成 —— 不要手改。",
            " * 探针，不是产品（验收线 § 3.1）。",
            " * 目标：VEX V5 Brain（ARMv7-A，ARM 态）· AAPCS · 整数子集（softfp 天然满足）。",
            " */",
            "    .syntax unified",
            "    .arm",
            "    .text",
        ]
        for d in root.children:
            if d.kind == "FUNC_DECL":
                if d.get("extern") == "1":
                    continue          # extern fn 由链接期解析，不用发原型
                out += self.func(d)
            elif d.kind == "TYPE_DECL":
                continue              # struct：B 路暂不支持
            elif d.kind == "MODULE":
                continue
            else:
                raise AsmError(f"模块级不支持 {d.kind}")
        if self.rodata:
            out += ["    .section .rodata"]
            out += self.rodata
        out += ["    .ltorg"]         # ldr r0,=label 的字面量池
        return "\n".join(out) + "\n"


# ── 自测 ────────────────────────────────────────────────────────────────
SELF_TEST_SRC = """MODULE @t.jhyy:1:1 no_std=0 ndecls=1
  FUNC_DECL @t.jhyy:1:1 name=main_jhyy nparams=0 extern=0 inline=0 naked=0
    RET
      IDENT @t.jhyy:1:19 name=i32
    BLOCK @t.jhyy:1:1 nstmts=3
      LET @t.jhyy:2:5 mut=1 name=i
        IDENT @t.jhyy:2:16 name=i32
        INT @t.jhyy:2:22 value=0 prim=2
      LET @t.jhyy:3:5 mut=0 name=msg
        CAST @t.jhyy:3:15
          STRING @t.jhyy:3:15 chars="hi\\n" len=3
          UNARY @t.jhyy:3:26 op=*
            IDENT @t.jhyy:3:26 name=u8
      IF @t.jhyy:4:5
        BINARY @t.jhyy:4:8 op=>
          IDENT @t.jhyy:4:8 name=i
          INT @t.jhyy:4:12 value=0 prim=2
        BLOCK @t.jhyy:4:5 nstmts=1
          EXPR_STMT @t.jhyy:5:9
            ASSIGN @t.jhyy:5:9
              IDENT @t.jhyy:5:9 name=i
              BINARY @t.jhyy:5:13 op=+
                IDENT @t.jhyy:5:13 name=i
                INT @t.jhyy:5:17 value=1 prim=2
        BLOCK @t.jhyy:4:5 nstmts=1
          EXPR_STMT @t.jhyy:6:9
            ASSIGN @t.jhyy:6:9
              IDENT @t.jhyy:6:9 name=i
              INT @t.jhyy:6:18 value=7 prim=2
"""


# 绑定面表里的 extern fn（★ enum 返回 ⇒ 掩码）
SELF_TEST_SRC_BINDING = """MODULE @tb.jhyy:1:1 no_std=0 ndecls=2
  FUNC_DECL @tb.jhyy:1:1 name=vexDeviceMotorBrakeModeGet nparams=1 extern=1 inline=0 naked=0
    PARAM name=dev
      UNARY @tb.jhyy:1:1 op=*
        IDENT @tb.jhyy:1:1 name=u8
    RET
      IDENT @tb.jhyy:1:1 name=i32
  FUNC_DECL @tb.jhyy:2:1 name=main_jhyy nparams=0 extern=0 inline=0 naked=0
    RET
      IDENT @tb.jhyy:2:19 name=i32
    BLOCK @tb.jhyy:2:1 nstmts=1
      LET @tb.jhyy:3:5 mut=0 name=b
        CALL @tb.jhyy:3:5
          IDENT @tb.jhyy:3:5 name=vexDeviceMotorBrakeModeGet
          INT @tb.jhyy:3:5 value=0 prim=2
"""


def self_test() -> int:
    asm = AsmEmitter().emit(parse(SELF_TEST_SRC))

    expect = [
        "    .global main",              # 入口符号 = main
        "    .type main, %function",
        "main:",
        "    push {r4-r11, lr}",         # 序言
        "    sub sp, sp, #",             # 栈帧
        "    movw r0, #0",               # 常量
        "    movt r0, #0",
        "    str r0, [sp, #",            # 变量写回
        "    ldr r0, [sp, #",            # 变量读出
        "    add r0, r0, r1",            # 加法
        "    cmp r0, #0",                # 比较
        "    beq ",                      # 条件跳转
        "    ldm sp!, {r4-r11, pc}",     # 返回
    ]
    for e in expect:
        assert e in asm, f"汇编里缺：{e!r}\n---- 实际 ----\n{asm}"

    # 字符串常量进 .rodata
    assert "    .section .rodata" in asm, asm
    assert '    .ascii "hi\\n"' in asm, asm

    # ★ 绑定面：extern fn 从表里查 ABI ⇒ enum 返回必须掩码
    asm2 = AsmEmitter().emit(parse(SELF_TEST_SRC_BINDING))
    assert "    bl vexDeviceMotorBrakeModeGet" in asm2, asm2
    assert "    and r0, r0, #0xff" in asm2, asm2

    # ★ extern fn 不在绑定面表里 ⇒ **报错**（B 路不猜 ABI）
    try:
        AsmEmitter().emit(parse(
            SELF_TEST_SRC_BINDING.replace("name=vexDeviceMotorBrakeModeGet",
                                          "name=vexDeviceNotInTheTable")))
    except AsmError as e:
        assert "不在绑定面表里" in str(e), e
    else:
        raise AssertionError("绑定面表里没有的 extern fn 应该报错")

    print("✔ 自测通过：入口改名 / 序言 / 栈帧 / 常量 / 变量 / 算术 / 比较 / 分支 / 返回 / "
          ".rodata / 绑定面表 / enum 掩码")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="jhyy dump 的 AST → ARM 汇编")
    ap.add_argument("dump", type=Path, nargs="?", help="dump 文本文件（- 表示 stdin）")
    ap.add_argument("-o", type=Path, help="输出文件（默认 stdout）")
    ap.add_argument("--self-test", action="store_true", help="自测")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.dump is None:
        ap.error("需要 dump 文件（或用 --self-test）")

    text = sys.stdin.read() if str(args.dump) == "-" else args.dump.read_text(encoding="utf-8")
    try:
        asm = AsmEmitter().emit(parse(text))
    except AsmError as e:
        print(f"asm emitter 不支持：{e}", file=sys.stderr)
        return 2

    if args.o:
        args.o.write_text(asm, encoding="utf-8", newline="\n")
        print(f"✔ 已写入 {args.o}")
    else:
        print(asm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
