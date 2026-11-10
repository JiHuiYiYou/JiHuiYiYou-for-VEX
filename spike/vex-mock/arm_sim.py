#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arm_sim.py —— **emitter 输出的 ARM 汇编**的小解释器（host 侧）

**为什么需要它**

A 路（JHYY → C）能在 host 上跑（`run-host.sh`）⇒ 可以跟 mock 比调用轨迹。
但 **B 路（JHYY → ARM 机器码）跑不了** ⇒ 它的**逻辑**（比较、跳转、参数顺序）
在 PC 上**没有任何验证**。

⚠️ 实测已经证明这很危险：**`<` / `>` 的操作数顺序写反了**，
静态门（比「调用集合 + 顺序」）**完全看不出来** —— 两路调的是同一批函数、
顺序也一样，但 `v2 < 0` 在 B 路被算成了 `v2 > 0` ⇒ 真机上 `REVF FLIP`
会被打成 `REVF SAME` ⇒ 三份屏显不一致 ⇒ 白跑一趟实验室。

⇒ 本模块让 B 路**也能在 host 上跑** ⇒ A/B **行为**对拍（比调用轨迹 + 屏显）
⇒ B 路的逻辑错误在 PC 上就被抓住。

**它只支持 emitter 真正会发出的那 18 条指令**（不是通用模拟器）：

    push pop movw movt mov cmp ldr str add sub mul rsb and
    b beq bne bl ldm

遇到不认识的指令 ⇒ **直接报错**（不猜、不静默跳过）——
「模拟器没覆盖到」必须看得见，否则就成了恒绿的假信号。
"""

import re

MASK = 0xFFFFFFFF
SIGN = 0x80000000


class SimError(Exception):
    """模拟器看不懂/跑不动 ⇒ 抛这个（绝不静默跳过）。"""


class ProgramExit(Exception):
    """程序正常返回（`ldm sp!, {..., pc}`）或到达模拟时钟上限。"""


def _to_signed(v):
    v &= MASK
    return v - 0x100000000 if v & SIGN else v


def _flags_sub(a, b):
    """`cmp a, b` 的标志位：返回 (N, Z, C, V)。"""
    a &= MASK
    b &= MASK
    res = (a - b) & MASK
    sr = _to_signed(a) - _to_signed(b)
    v = 1 if (sr < -0x80000000 or sr > 0x7FFFFFFF) else 0
    n = 1 if res & SIGN else 0
    z = 1 if res == 0 else 0
    c = 1 if a >= b else 0
    return n, z, c, v


def _cond_holds(cond, n, z, c, v):
    if cond == "eq":
        return z == 1
    if cond == "ne":
        return z == 0
    if cond == "lt":
        return n != v
    if cond == "le":
        return z == 1 or n != v
    if cond == "gt":
        return z == 0 and n == v
    if cond == "ge":
        return n == v
    if cond == "lo":
        return c == 0
    if cond == "ls":
        return c == 0 or z == 1
    if cond == "hi":
        return c == 1 and z == 0
    if cond == "hs":
        return c == 1
    raise SimError("不认识的条件码 %r" % cond)


COND_SUFFIXES = ("eq", "ne", "lt", "le", "gt", "ge", "lo", "ls", "hi", "hs")

# 寄存器名 → 编号
REG_NUM = {"r%d" % i: i for i in range(13)}
REG_NUM["sp"] = 13
REG_NUM["lr"] = 14
REG_NUM["pc"] = 15


class ArmSim:
    """跑 emitter 产出的汇编。

    用法：
        sim = ArmSim(stubs)          # stubs: {函数名: fn(sim, args) -> int|None}
        sim.load(asm_text)
        sim.run("main")
        print(sim.trace_text())
        print(sim.screen_text())
    """

    MEM_SIZE = 1 << 16
    SP_START = 0x8000
    MAX_STEPS = 2_000_000

    def __init__(self, stubs):
        self.stubs = stubs
        self.regs = [0] * 16
        self.regs[13] = self.SP_START        # sp（r13）
        self.mem = bytearray(self.MEM_SIZE)
        self.pc = 0
        self.flags = (0, 0, 0, 0)
        self.instrs = []
        self.labels = {}
        self.strings = {}          # 标签 → 字符串
        self.addr_of = {}         # 标签 → 伪地址
        self.str_at = {}          # 伪地址 → 字符串

    # ── 解析 ──────────────────────────────────────────────────────────
    def load(self, text):
        text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
        text = re.sub(r"//[^\n]*", " ", text)

        cur_label = None
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            # 可能是 `标签:` 或 `标签: 指令`
            m = re.match(r"^([A-Za-z_.$][\w.$]*):\s*(.*)$", line)
            if m and m.group(2) != "" and not re.match(r"^[A-Za-z]", m.group(2)):
                m = None                      # 不是标签（例如 `cmp r0, #0`）
            if m:
                cur_label = m.group(1)
                # 标签指向**下一条指令**（指令表的下标 = 当前长度）
                self.labels[cur_label] = len(self.instrs)
                line = m.group(2).strip()
                if not line:
                    continue
            if line.startswith("."):
                m2 = re.match(r'^\.ascii\s+"(.*)"\s*$', line)
                if m2 and cur_label:
                    self.strings[cur_label] = m2.group(1)
                continue
            self.instrs.append(line)

        # 字符串的伪地址（`ldr r0, =strN` 取的就是它）
        for i, name in enumerate(self.strings):
            addr = 0x1000 + i * 0x40
            self.addr_of[name] = addr
            self.str_at[addr] = self.strings[name]

    # ── 内存 ──────────────────────────────────────────────────────────
    def _read32(self, addr):
        a = addr & MASK
        # ⚠️ 越界必须**报错**：Python 的切片赋值越界会**静默无效** ⇒
        #    内存看起来全是 0，而程序照跑不误 ⇒ 恒绿的假信号。
        if a + 4 > self.MEM_SIZE:
            raise SimError("读越界：地址 0x%x（模拟器内存只有 %d 字节）"
                           % (a, self.MEM_SIZE))
        return int.from_bytes(self.mem[a:a + 4], "little")

    def _write32(self, addr, val):
        a = addr & MASK
        if a + 4 > self.MEM_SIZE:
            raise SimError("写越界：地址 0x%x（模拟器内存只有 %d 字节）"
                           % (a, self.MEM_SIZE))
        self.mem[a:a + 4] = (val & MASK).to_bytes(4, "little")

    # ── 寄存器读写 ────────────────────────────────────────────────────
    def _get(self, name):
        return self.regs[REG_NUM[name]] & MASK

    def _set(self, name, val):
        self.regs[REG_NUM[name]] = val & MASK

    # ── 执行 ──────────────────────────────────────────────────────────
    def run(self, entry="main"):
        if entry not in self.labels:
            raise SimError("找不到入口符号 %r（有的标签：%s）"
                           % (entry, ", ".join(sorted(self.labels)[:8])))
        self.pc = self.labels[entry]
        steps = 0
        while True:
            steps += 1
            if steps > self.MAX_STEPS:
                raise SimError("步数超限（%d）—— 可能有死循环" % self.MAX_STEPS)
            line = self.instrs[self.pc]
            if line is None:                 # 纯标签 ⇒ 跳到下一条
                self.pc += 1
                continue
            self.pc += 1
            self._exec(line)

    def _exec(self, line):
        op, _, rest = line.partition(" ")
        rest = rest.strip()

        # 条件执行的 mov（movgt / moveq / movlt / movne …）
        for suf in COND_SUFFIXES:
            if op.startswith("mov") and op != "mov" and op[3:] in COND_SUFFIXES:
                cond = op[3:]
                a, b = self._two_ops(rest)
                if _cond_holds(cond, *self.flags):
                    self._set(a, self._value(b))
                return

        if op == "movw":
            a, b = self._two_ops(rest)
            self._set(a, self._value(b) & 0xFFFF)
            return
        if op == "movt":
            a, b = self._two_ops(rest)
            hi = (self._value(b) & 0xFFFF) << 16
            self._set(a, (self._get(a) & 0xFFFF) | hi)
            return
        if op == "mov":
            a, b = self._two_ops(rest)
            self._set(a, self._value(b))
            return
        if op == "cmp":
            a, b = self._two_ops(rest)
            self.flags = _flags_sub(self._get(a), self._value(b))
            return
        if op in ("add", "sub", "mul", "and", "orr", "eor", "rsb"):
            a, b, c = self._three_ops(rest)
            x = self._get(b)
            y = self._value(c)
            if op == "add":
                r = x + y
            elif op == "sub":
                r = x - y
            elif op == "mul":
                r = x * y
            elif op == "and":
                r = x & y
            elif op == "orr":
                r = x | y
            elif op == "eor":
                r = x ^ y
            else:                       # rsb: r = y - x
                r = y - x
            self._set(a, r)
            return
        if op == "push":
            # ARM：`push {r4-r11, lr}` = STMDB ⇒ **编号小的寄存器在低地址**
            regs = self._reglist(rest)
            self.regs[13] = (self.regs[13] - 4 * len(regs)) & MASK
            for i, reg in enumerate(regs):
                self._write32((self.regs[13] + 4 * i) & MASK, self.regs[reg])
            return
        if op == "pop":
            # LDMIA：编号小的寄存器在低地址 ⇒ 与 push 一一对应
            regs = self._reglist(rest)
            for i, reg in enumerate(regs):
                self.regs[reg] = self._read32((self.regs[13] + 4 * i) & MASK)
            self.regs[13] = (self.regs[13] + 4 * len(regs)) & MASK
            return
        if op == "ldm":
            # 只支持 `ldm sp!, {r4-r11, pc}`
            if not rest.startswith("sp!"):
                raise SimError("只支持 `ldm sp!, {...}`，收到 %r" % rest)
            regs = self._reglist(rest)
            vals = []
            for reg in regs:
                vals.append(self._read32(self.regs[13]))
                self.regs[13] = (self.regs[13] + 4) & MASK
            for reg, val in zip(regs, vals):
                self.regs[reg] = val & MASK
            if 15 in regs:                # pc ⇒ 返回
                raise ProgramExit(self.regs[0])
            return
        if op == "ldr":
            a, b = self._two_ops(rest)
            self._set(a, self._load_addr(b))
            return
        if op == "str":
            a, b = self._two_ops(rest)
            self._store_addr(b, self._get(a))
            return
        if op in ("b", "beq", "bne", "blt", "bgt", "ble", "bge"):
            target = rest.strip()
            if op != "b":
                cond = op[1:]
                if not _cond_holds(cond, *self.flags):
                    return
            if op == "bl":
                raise SimError("bl 到本地标签没实现：%r" % target)
            if target not in self.labels:
                raise SimError("找不到标签 %r" % target)
            self.pc = self.labels[target]
            return
        if op == "bl":
            return self._call(rest.strip())
        raise SimError("模拟器不认识这条指令：%r" % line)

    # ── 外部调用 ──────────────────────────────────────────────────────
    def _call(self, name):
        fn = self.stubs.get(name)
        if fn is None:
            raise SimError("没有为 %r 提供桩函数（模拟器不猜 ABI）" % name)
        args = [self.regs[i] for i in range(4)]
        ret = fn(self, args)
        if ret is not None:
            self.regs[0] = ret & MASK

    # ── 操作数 ────────────────────────────────────────────────────────
    def _two_ops(self, rest):
        a, _, b = rest.partition(",")
        return a.strip(), b.strip()

    def _three_ops(self, rest):
        parts = [p.strip() for p in rest.split(",")]
        if len(parts) != 3:
            raise SimError("要 3 个操作数，收到 %r" % rest)
        return parts[0], parts[1], parts[2]

    def _value(self, operand):
        """操作数 → 立即数（只支持 `#imm`；寄存器在调用处单独处理）。"""
        operand = operand.strip()
        if operand.startswith("#"):
            txt = operand[1:].strip()
            try:
                if txt.lower().startswith("0x"):
                    return int(txt, 16)
                return int(txt, 10)
            except ValueError:
                raise SimError("看不懂的立即数 %r" % operand)
        if operand in REG_NUM:
            return self._get(operand)
        raise SimError("看不懂的操作数 %r" % operand)

    def _reglist(self, rest):
        """`{r0}` / `{r4-r11, lr}` → [编号, …]（升序，与 ARM 压栈顺序一致）。

        也接受**已经剥掉花括号**的 `r4-r11, pc`。
        """
        rest = rest.strip()
        inner = rest[rest.index("{") + 1:rest.index("}")] if "{" in rest else rest
        out = []
        for part in [p.strip() for p in inner.split(",") if p.strip()]:
            if "-" in part:
                lo, hi = part.split("-")
                lo_n = REG_NUM[lo.strip()]
                hi_n = REG_NUM[hi.strip()]
                out.extend(range(lo_n, hi_n + 1))
            else:
                out.append(REG_NUM[part])
        return out

    def _load_addr(self, operand):
        operand = operand.strip()
        if operand.startswith("="):
            label = operand[1:].strip()
            if label not in self.addr_of:
                raise SimError("没有字符串标签 %r" % label)
            return self.addr_of[label]
        m = re.match(r"^\[\s*sp\s*(?:,\s*#(-?\d+))?\s*\]$", operand)
        if m:
            off = int(m.group(1) or 0)
            return self._read32((self.regs[13] + off) & MASK)
        raise SimError("看不懂的 ldr 操作数 %r" % operand)

    def _store_addr(self, operand, val):
        m = re.match(r"^\[\s*sp\s*(?:,\s*#(-?\d+))?\s*\]$", operand.strip())
        if not m:
            raise SimError("看不懂的 str 操作数 %r" % operand)
        off = int(m.group(1) or 0)
        self._write32((self.regs[13] + off) & MASK, val)

    # ── 输出 ──────────────────────────────────────────────────────────
    # ⚠️ **轨迹与屏显文字只有一份真相源**：`mock_model.MockModel`
    #    （桩函数自己往模型里记）⇒ 模拟器不再另记一份 ⇒ 不会两边打架。


# ── 自测 ────────────────────────────────────────────────────────────────
# 一段**手写**的小程序：把几个比较的结果交给桩函数 `emit`。
# 断言的是**算出来的值**，不是文本 ⇒ 解释器算错就红。
SELF_TEST_ASM = """    .syntax unified
    .arm
    .text
    .global main
    .type main, %function
main:
    push {r4-r11, lr}
    sub sp, sp, #16
    movw r0, #7
    movt r0, #0
    str r0, [sp, #0]
    movw r0, #3
    movt r0, #0
    str r0, [sp, #4]
    movw r0, #65531
    movt r0, #65535
    str r0, [sp, #8]
    ldr r0, [sp, #0]
    ldr r2, [sp, #4]
    push {r0}
    mov r1, r2
    pop {r0}
    cmp r0, r1
    mov r0, #0
    movlt r0, #1
    bl emit
    ldr r0, [sp, #0]
    ldr r2, [sp, #4]
    push {r0}
    mov r1, r2
    pop {r0}
    cmp r0, r1
    mov r0, #0
    movgt r0, #1
    bl emit
    ldr r0, [sp, #4]
    ldr r2, [sp, #0]
    push {r0}
    mov r1, r2
    pop {r0}
    cmp r0, r1
    mov r0, #0
    movlt r0, #1
    bl emit
    ldr r0, [sp, #0]
    ldr r2, [sp, #4]
    push {r0}
    mov r1, r2
    pop {r0}
    cmp r0, r1
    mov r0, #0
    moveq r0, #1
    bl emit
    ldr r0, [sp, #8]
    ldr r2, [sp, #4]
    push {r0}
    mov r1, r2
    pop {r0}
    cmp r0, r1
    mov r0, #0
    movlt r0, #1
    bl emit
    ldr r0, [sp, #8]
    ldr r2, [sp, #4]
    push {r0}
    mov r1, r2
    pop {r0}
    cmp r0, r1
    mov r0, #0
    movgt r0, #1
    bl emit
    mov r0, #0
    add sp, sp, #16
    ldm sp!, {r4-r11, pc}
"""


def self_test() -> int:
    got = []

    def emit(sim, args):
        got.append(args[0])
        return None

    sim = ArmSim({"emit": emit})
    sim.load(SELF_TEST_ASM)
    try:
        sim.run("main")
    except ProgramExit:
        pass          # `ldm sp!, {..., pc}` = 函数返回（预期）

    # 7 / 3 / -5
    #   7 < 3 假 | 7 > 3 真 | 3 < 7 真 | 7 == 3 假 | -5 < 3 真 | -5 > 3 假
    want = [0, 1, 1, 0, 1, 0]
    assert got == want, "比较算错了：期望 %s，实际 %s" % (want, got)

    # ★ 栈帧必须自己还回去（少了 `add sp` ⇒ 返回地址从垃圾里读）
    assert sim.regs[13] == ArmSim.SP_START, \
        "返回后 sp 没回到入口值（%d ≠ %d）—— 尾声少还了栈帧？" % (sim.regs[13],
                                                               ArmSim.SP_START)

    print("✔ 自测通过：比较（lt/gt/eq，负数）/ 栈帧 / push-pop")
    return 0


if __name__ == "__main__":
    import sys
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    print("arm_sim.py 是模块；用 `python arm_sim.py --self-test` 跑自测", file=sys.stderr)
    sys.exit(2)
