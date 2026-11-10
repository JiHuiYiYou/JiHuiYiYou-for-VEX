#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""binding_surface.py —— **绑定面表（唯一真相源）**

一个 `extern fn` 要同时对三件事负责：

| 面向 | 谁看 | 用途 |
|---|---|---|
| **JHYY 声明** | 主仓编译器 | 程序里怎么写这个函数 |
| **C 原型** | clang | 生成的 C 源码里发什么原型 |
| **ABI** | B 路 emitter | 传几个寄存器、返回多宽、要不要掩码 |

以前这三件事散在三个地方（事实基线 § 9.2 / `emit_c.py` / `asm_emit.py`）⇒ **必然漂移**。
现在收成**一张表**：

* `emit_c.py`（A 路）读它 → **发原型** ⇒ `v5.h` 会逐字校验 ⇒
  **C 编译器就是绑定面 ABI 的检查器**。
* `asm_emit.py`（B 路）读它 → 推 AAPCS 的传参/返回宽度。
* `scripts/check-artifacts.sh` / `--check-sdk` 读它 → **与 SDK 头文件逐字比对**。

⚠️ **为什么不直接绑 VEX 的 enum 函数？**
   `vexDeviceMotorGearingSet(V5_DeviceT, V5MotorGearset)` 的第二个形参是 **enum**，
   而 JHYY 的 FFI **不支持 enum 跨边界**（ABI v4.0.0 § 6）⇒
   JHYY 侧只能传 `i32`，**由 C 侧隐式转成 enum**。
   ⇒ 语义上要求「JHYY 传的整数 = enum 的序号」⇒ 序号表记在下面 `ENUMS` 里。

⚠️ **enum 实参为什么安全？**
   AAPCS：小于 4 字节的实参放在 r0–r3 的**低字节**，高位未定义。
   ⇒ 我们**总是传零扩展的 32 位值** ⇒
   ① callee 按 1 字节读（`-fshort-enums`）→ 读到低字节 ✔
   ② callee 按 4 字节读（没开 `-fshort-enums`）→ 读到整个字 ✔
   **两种情况都对** ⇒ 这是本表里 enum 敢直接绑的前提。

⚠️ **enum 返回为什么必须掩码？**
   1 字节 enum 返回时 **r0 的高 3 字节未定义** ⇒ B 路必须 `and r0, r0, #0xff`。
   （A 路不用管 —— clang 自己知道 enum 的宽度。）
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ── enum 序号表（JHYY 传的整数 ↔ SDK 的 enum 成员）────────────────────────
# ⚠️ 这些序号**不是** JHYY 的类型 —— 只是「JHYY 传这个整数 ⇒ C 侧转成这个成员」。
#    取值来自 `v5_apitypes.h`（实测，见事实基线 § 9.1）。
ENUMS: dict[str, dict[int, str]] = {
    "V5MotorGearset": {
        0: "kMotorGearSet_36",
        1: "kMotorGearSet_18",
        2: "kMotorGearSet_06",
    },
    "V5MotorBrakeMode": {
        0: "kV5MotorBrakeModeCoast",
        1: "kV5MotorBrakeModeBrake",
        2: "kV5MotorBrakeModeHold",
    },
    "V5MotorEncoderUnits": {
        0: "kMotorEncoderDegrees",
        1: "kMotorEncoderRotations",
        2: "kMotorEncoderCounts",
    },
}

# 1 字节的 enum（`-fshort-enums` 实测，事实基线 § 9.1）
SHORT_ENUM_TYPES = {"V5MotorGearset", "V5MotorBrakeMode", "V5MotorEncoderUnits"}


@dataclass(frozen=True)
class Binding:
    """绑定面里的一个函数。"""

    name: str
    # ── JHYY 侧 ──
    jhyy_params: tuple[tuple[str, str], ...]   # (形参名, JHYY 类型)
    jhyy_ret: str                              # "" = void
    # ── C 侧（**逐字**抄自 SDK，或抄我们自己的封装头）──
    c_ret: str
    c_params: tuple[tuple[str, str], ...]      # (形参名, C 类型)
    # ── 其它 ──
    kind: str = "direct"        # direct = 直接绑 SDK 的符号；wrapper = 我们自己的封装
    ret_enum: bool = False      # 返回值是 enum ⇒ B 路要掩码
    note: str = ""
    enum_arg: tuple[str, int] | None = None    # (enum 类型名, 实参位置)

    # ── 派生 ──────────────────────────────────────────────────────────
    @property
    def jhyy_decl(self) -> str:
        """JHYY 侧的 `extern fn` 声明（一行）。"""
        ps = ", ".join(f"{n}: {t}" for n, t in self.jhyy_params)
        ret = f" -> {self.jhyy_ret}" if self.jhyy_ret else ""
        return f"extern fn {self.name}({ps}){ret};"

    @property
    def c_proto(self) -> str:
        """C 侧的原型（一行，带分号）—— 生成的 C 源码里**逐字**发这个。"""
        ps = ", ".join(c_decl(t, n) for n, t in self.c_params)
        return f"{c_ret(self.c_ret)} {self.name}({ps or 'void'});"

    @property
    def c_signature(self) -> tuple[str, list[str]]:
        """(返回类型, [形参类型]) —— 忽略形参名，用于跟 SDK 头文件比对。"""
        return self.c_ret, [t for _, t in self.c_params]

    def enum_arg_note(self) -> str:
        if self.enum_arg is None:
            return ""
        etype, pos = self.enum_arg
        members = ENUMS.get(etype, {})
        items = ", ".join(f"{v}={members.get(v, '?')}" for v in sorted(members))
        return f"第 {pos + 1} 个实参是 {etype}（{items}）"

    def abi_note(self) -> str:
        """B 路要用的 ABI 摘要（写进文档 / 自测用）。"""
        widths = []
        for _, jt in self.jhyy_params:
            widths.append(jhyy_width(jt))
        ret_w = jhyy_width(self.jhyy_ret) if self.jhyy_ret else 0
        mask = "（enum 返回 ⇒ 掩码 0xff）" if self.ret_enum else ""
        return (f"实参 {widths} ⇒ 寄存器 r0..r{len(widths) - 1}；"
                f"返回 {ret_w or 'void'} 字节{mask}")


def c_ret(t: str) -> str:
    return t


def c_decl(c_type: str, name: str) -> str:
    """C 的形参声明：`int32_t x` / `const char *text`。"""
    if c_type.endswith("*"):
        return f"{c_type}{name}"
    return f"{c_type} {name}"


def jhyy_width(jt: str) -> int:
    """JHYY 类型 → 字节宽（B 路用；ARM 目标指针 4 字节，事实基线 § 8.1 末尾）。"""
    if not jt:
        return 0
    if jt.startswith("*"):
        return 4
    return {
        "i8": 1, "u8": 1, "bool": 1,
        "i16": 2, "u16": 2,
        "i32": 4, "u32": 4,
        "i64": 8, "u64": 8, "f32": 4, "f64": 8,
    }.get(jt, 4)


# ── 表本体 ───────────────────────────────────────────────────────────────
BINDINGS: list[Binding] = [
    Binding(
        name="vexDeviceGetByIndex",
        jhyy_params=(("index", "u32"),),
        jhyy_ret="*u8",
        c_ret="V5_DeviceT",
        c_params=(("index", "uint32_t"),),
        note="设备句柄。索引 0 = PORT1。C 侧是**不透明指针**（4 字节）⇒ "
             "JHYY 侧映射 `*u8`（不要写类型标注，让推导给 C 类型）。",
    ),
    Binding(
        name="vexDeviceMotorGearingSet",
        jhyy_params=(("dev", "*u8"), ("gear", "i32")),
        jhyy_ret="",
        c_ret="void",
        c_params=(("device", "V5_DeviceT"), ("value", "V5MotorGearset")),
        enum_arg=("V5MotorGearset", 1),
        note="齿轮组。JHYY 传**序号**（0=36:1 / 1=18:1 / 2=6:1）⇒ "
             "C 侧隐式转成 enum（见 ENUMS）。",
    ),
    Binding(
        name="vexDeviceMotorBrakeModeSet",
        jhyy_params=(("dev", "*u8"), ("mode", "i32")),
        jhyy_ret="",
        c_ret="void",
        c_params=(("device", "V5_DeviceT"), ("mode", "V5MotorBrakeMode")),
        enum_arg=("V5MotorBrakeMode", 1),
        note="刹车模式。JHYY 传序号（0=Coast / 1=Brake / 2=Hold）。",
    ),
    Binding(
        name="vexDeviceMotorEncoderUnitsSet",
        jhyy_params=(("dev", "*u8"), ("units", "i32")),
        jhyy_ret="",
        c_ret="void",
        c_params=(("device", "V5_DeviceT"), ("units", "V5MotorEncoderUnits")),
        enum_arg=("V5MotorEncoderUnits", 1),
        note="编码器单位。JHYY 传序号（0=Degrees / 1=Rotations / 2=Counts）。",
    ),
    Binding(
        name="vexDeviceMotorVelocitySet",
        jhyy_params=(("dev", "*u8"), ("velocity", "i32")),
        jhyy_ret="",
        c_ret="void",
        c_params=(("device", "V5_DeviceT"), ("velocity", "int32_t")),
        note="速度命令。**单位 = RPM**（事实基线 § 9.7 实测）。",
    ),
    Binding(
        name="vexDeviceMotorBrakeModeGet",
        jhyy_params=(("dev", "*u8"),),
        jhyy_ret="i32",
        c_ret="V5MotorBrakeMode",
        c_params=(("device", "V5_DeviceT"),),
        ret_enum=True,
        note="★ **enum 返回** ⇒ r0 的高 3 字节未定义 ⇒ B 路必须掩码 0xff；"
             "A 路由 clang 负责。",
    ),
    Binding(
        name="vexDeviceAbsEncVelocityGet",
        jhyy_params=(("dev", "*u8"),),
        jhyy_ret="i32",
        c_ret="int32_t",
        c_params=(("device", "V5_DeviceT"),),
        note="**绝对编码器**的实测速度（RPM，整数）⇒ 用来判断「电机到底转没转」。"
             "（`vexDeviceMotorVelocityGet` 返回的是**命令值**，不是实测值。）",
    ),
    Binding(
        name="vexDelay",
        jhyy_params=(("ms", "u32"),),
        jhyy_ret="",
        c_ret="void",
        c_params=(("timems", "uint32_t"),),
        note="毫秒延时。",
    ),
    Binding(
        name="jhyy_vex_display_puts",
        jhyy_params=(("xpos", "i32"), ("ypos", "i32"), ("text", "*u8")),
        jhyy_ret="",
        c_ret="void",
        c_params=(("xpos", "int32_t"), ("ypos", "int32_t"), ("text", "const char *")),
        kind="wrapper",
        note="★ **我们自己的封装**（不是变参的 vexDisplayPrintf）："
             "JHYY 不支持变参调用（ABI v4.0.0 § 6）⇒ 变参只发生在 C 内部。"
             "坐标单位 = **像素**（实测）；bOpaque 固定 1（事实基线 § 9.4 / § 9.6）。"
             "A 路与 B 路调**同一个符号**。",
    ),
]

BY_NAME: dict[str, Binding] = {b.name: b for b in BINDINGS}


def lookup(name: str) -> Binding | None:
    return BY_NAME.get(name)


# ── 与 SDK 头文件比对 ────────────────────────────────────────────────────
_PROTO_RE = re.compile(
    r"^\s*(?P<ret>[A-Za-z_][A-Za-z0-9_ \*]*?)\s+"
    r"(?P<name>vex[A-Za-z0-9_]+)\s*\((?P<args>[^;]*)\)\s*;\s*$"
)


def normalize_signature(ret: str, args: str) -> tuple[str, list[str]]:
    """(返回类型, [形参类型]) —— 忽略名字与空白，用来跟 SDK 头文件比对。"""
    r = " ".join(ret.split())
    if r.endswith("*"):
        r = r[:-1].rstrip() + " *"
    out: list[str] = []
    for a in args.split(","):
        a = a.strip()
        if not a or a == "void":
            continue
        # 去掉形参名：类型 + 名字 ⇒ 只留类型
        m = re.match(r"^(.*?)([A-Za-z_][A-Za-z0-9_]*)$", a)
        if m:
            t = m.group(1).strip()
        else:
            t = a
        t = " ".join(t.split())
        if t.endswith("*"):
            t = t[:-1].rstrip() + " *"
        out.append(t)
    return r, out


def scan_sdk_headers(headers: list[Path]) -> dict[str, tuple[str, list[str]]]:
    """扫 SDK 头文件 ⇒ {函数名: (返回类型, [形参类型])}。"""
    found: dict[str, tuple[str, list[str]]] = {}
    for h in headers:
        if not h.exists():
            continue
        for line in h.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _PROTO_RE.match(line)
            if not m:
                continue
            ret, args = normalize_signature(m.group("ret"), m.group("args"))
            found[m.group("name")] = (ret, args)
    return found


def check_against_sdk(headers: list[Path]) -> list[str]:
    """表里的每个 direct 条目都必须与 SDK 头文件**逐字**一致 ⇒ 返回问题清单。"""
    sdk = scan_sdk_headers(headers)
    problems: list[str] = []
    for b in BINDINGS:
        if b.kind != "direct":
            continue
        if b.name not in sdk:
            problems.append(f"{b.name}：SDK 头文件里**找不到**这个函数")
            continue
        got = sdk[b.name]
        want = b.c_signature
        if got != want:
            problems.append(
                f"{b.name}：与 SDK 头文件不一致\n"
                f"    表里：{want}\n"
                f"    SDK ：{got}"
            )
    return problems


# ── 自测 ────────────────────────────────────────────────────────────────
def self_test() -> int:
    # 1. 表里的名字唯一
    names = [b.name for b in BINDINGS]
    assert len(names) == len(set(names)), f"表里有重名：{names}"

    # 2. JHYY 声明派生正确
    b = BY_NAME["vexDeviceGetByIndex"]
    assert b.jhyy_decl == "extern fn vexDeviceGetByIndex(index: u32) -> *u8;", b.jhyy_decl
    assert b.c_proto == "V5_DeviceT vexDeviceGetByIndex(uint32_t index);", b.c_proto

    b2 = BY_NAME["jhyy_vex_display_puts"]
    assert b2.c_proto == \
        "void jhyy_vex_display_puts(int32_t xpos, int32_t ypos, const char *text);", b2.c_proto

    b3 = BY_NAME["vexDeviceMotorGearingSet"]
    assert b3.c_proto == \
        "void vexDeviceMotorGearingSet(V5_DeviceT device, V5MotorGearset value);", b3.c_proto

    # 3. 没有形参的 C 原型要写 `void`（不是空括号）
    assert BY_NAME["vexDelay"].c_proto == "void vexDelay(uint32_t timems);", \
        BY_NAME["vexDelay"].c_proto
    zero = Binding(name="f", jhyy_params=(), jhyy_ret="", c_ret="void", c_params=())
    assert zero.c_proto == "void f(void);", zero.c_proto

    # 4. enum 返回的条目必须标 ret_enum，且 enum 类型在 SHORT_ENUM_TYPES 里
    for b in BINDINGS:
        if b.ret_enum:
            assert b.c_ret in SHORT_ENUM_TYPES, f"{b.name} 的返回类型 {b.c_ret} 不在短 enum 名单里"
        if b.enum_arg:
            etype = b.enum_arg[0]
            assert etype in ENUMS, f"{b.name} 的 enum 实参 {etype} 没登记序号"

    # 5. enum 实参的序号表必须与 SDK 一致（0/1/2）
    assert ENUMS["V5MotorGearset"][1] == "kMotorGearSet_18"
    assert ENUMS["V5MotorBrakeMode"][1] == "kV5MotorBrakeModeBrake"
    assert ENUMS["V5MotorEncoderUnits"][0] == "kMotorEncoderDegrees"

    # 6. 签名归一化：忽略形参名与空白
    r, args = normalize_signature("V5_DeviceT", "uint32_t index")
    assert (r, args) == ("V5_DeviceT", ["uint32_t"]), (r, args)
    r, args = normalize_signature("int32_t", "V5_DeviceT device, uint32_t *timestamp")
    assert (r, args) == ("int32_t", ["V5_DeviceT", "uint32_t *"]), (r, args)

    # 7. ABI 摘要
    assert "r0..r1" in BY_NAME["vexDeviceMotorVelocitySet"].abi_note()
    assert "掩码 0xff" in BY_NAME["vexDeviceMotorBrakeModeGet"].abi_note()

    # 8. JHYY 宽度
    assert jhyy_width("*u8") == 4 and jhyy_width("u32") == 4 and jhyy_width("i32") == 4

    print(f"✔ 自测通过：绑定面表 {len(BINDINGS)} 条"
          f"（direct {sum(1 for b in BINDINGS if b.kind == 'direct')}"
          f" / wrapper {sum(1 for b in BINDINGS if b.kind == 'wrapper')}）"
          f" / enum 返回 {sum(1 for b in BINDINGS if b.ret_enum)} 条")
    return 0


# ── markdown 输出（给文档用）────────────────────────────────────────────
def to_markdown() -> str:
    lines = [
        "| JHYY 声明 | C 原型（逐字） | 备注 |",
        "|---|---|---|",
    ]
    for b in BINDINGS:
        note = b.note
        if b.enum_arg:
            note += " " + b.enum_arg_note()
        if b.ret_enum:
            note += " ★ enum 返回 ⇒ B 路掩码 0xff。"
        lines.append(f"| `{b.jhyy_decl}` | `{b.c_proto}` | {note} |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="绑定面表（唯一真相源）")
    ap.add_argument("--self-test", action="store_true", help="自测")
    ap.add_argument("--list", action="store_true", help="输出 markdown 表")
    ap.add_argument("--check-sdk", type=Path, nargs="*", default=None,
                    help="跟 SDK 头文件比对（给头文件目录或文件列表）")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.list:
        print(to_markdown())
        return 0
    if args.check_sdk is not None:
        headers: list[Path] = []
        for p in args.check_sdk:
            if p.is_dir():
                headers += sorted(p.glob("*.h"))
            else:
                headers.append(p)
        problems = check_against_sdk(headers)
        if problems:
            print("❌ 绑定面表与 SDK 头文件不一致：", file=sys.stderr)
            for p in problems:
                print("  " + p, file=sys.stderr)
            return 1
        print(f"✔ 绑定面表与 SDK 头文件一致（扫了 {len(headers)} 个头文件）")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
