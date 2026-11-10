#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mock_model.py —— **C 版 mock（`vex_mock.c`）的 Python 镜像**

**为什么有两份模型**

A 路（JHYY → C）在 host 上跑，用的是 **C 版 mock**；
B 路（JHYY → ARM 汇编）在 host 上跑，用 **arm_sim.py 解释器** + **本文件的 Python 模型**。

⇒ 两边各跑一遍 ⇒ **比调用轨迹 + 屏显文字** ⇒ A/B 行为对拍。

⚠️ **两份模型必须一模一样**（否则对拍出来的差异是"模型的差异"而不是"实现的差异"）
⇒ 本文件逐行对应 `vex_mock.c`（同样的 alpha、同样的四舍五入、同样的记录格式）。

**轨迹格式与 C 版逐字相同**（`%04d %s %d %d %d`）⇒ 两边可以直接 `diff`。
"""

from arm_sim import ProgramExit


class Motor:
    def __init__(self, port):
        self.port = port
        self.cmd_velocity = 0.0
        self.velocity = 0.0
        self.position = 0.0
        self.brake_mode = 0        # 0 Coast / 1 Brake / 2 Hold
        self.enc_units = 0         # 0 Degrees
        self.gear = 0              # 0 = 36:1
        self.rev_flag = 0


class MockModel:
    """与 `vex_mock.c` 的 `VexMock` 一一对应。"""

    def __init__(self, max_ms=3000.0):
        self.max_ms = float(max_ms)
        self.motors = [Motor(i) for i in range(8)]
        self.now_ms = 0.0
        self.screen = []
        self.trace = []

    # ── 轨迹 ──────────────────────────────────────────────────────────
    def rec(self, fn, a=0, b=0, c=0):
        self.trace.append((fn, a, b, c))

    def trace_text(self):
        out = []
        for i, (fn, a, b, c) in enumerate(self.trace):
            out.append("%04d %s %d %d %d" % (i, fn, a, b, c))
        return "".join(line + "\n" for line in out)

    def screen_text(self):
        return "".join(self.screen)

    # ── 假电机 ────────────────────────────────────────────────────────
    def advance(self, dt_ms):
        """与 `vex_mock.c` 的 `advance()` 逐行对应。"""
        alpha = dt_ms / (dt_ms + 100.0)
        for m in self.motors:
            target = float(m.cmd_velocity)
            # ⚠️ **反转标志会翻转命令方向**（SDK 文档：inverts the motor commands）
            if m.rev_flag:
                target = -target
            # 刹车：速度命令为 0 时按刹车模式处理（Brake/Hold ⇒ 直接停住）
            if target == 0.0 and m.brake_mode in (1, 2):
                m.velocity = 0.0
            else:
                m.velocity += (target - m.velocity) * alpha
            # 速度 RPM → 位置度：°/s = RPM × 6（事实基线 § 9.7 实测）
            m.position += m.velocity * 6.0 * (dt_ms / 1000.0)
        self.now_ms += dt_ms
        if self.now_ms > self.max_ms:
            # C 版在这里 `exit(0)`（atexit 打轨迹）⇒ 这里等价于"到此为止"
            raise ProgramExit(0)

    def _motor(self, dev):
        return self.motors[dev] if 0 <= dev < len(self.motors) else None


def make_stubs(model: MockModel):
    """返回 {函数名: fn(sim, args) -> int|None}（与 `vex_mock.c` 的 13 个函数对应）。"""

    def vexDeviceGetByIndex(sim, args):
        index = args[0] & 0xFFFFFFFF
        model.rec("vexDeviceGetByIndex", index, 0, 0)
        if index >= 8:
            index = 7
        return index                       # 句柄 = 端口序号（C 版是 &motor[i]）

    def vexDeviceMotorGearingSet(sim, args):
        dev, value = args[0], args[1]
        model.rec("vexDeviceMotorGearingSet", dev, value, 0)
        m = model._motor(dev)
        if m:
            m.gear = value

    def vexDeviceMotorBrakeModeSet(sim, args):
        dev, mode = args[0], args[1]
        model.rec("vexDeviceMotorBrakeModeSet", dev, mode, 0)
        m = model._motor(dev)
        if m:
            m.brake_mode = mode

    def vexDeviceMotorEncoderUnitsSet(sim, args):
        dev, units = args[0], args[1]
        model.rec("vexDeviceMotorEncoderUnitsSet", dev, units, 0)
        m = model._motor(dev)
        if m:
            m.enc_units = units

    def vexDeviceMotorVelocitySet(sim, args):
        dev, velocity = args[0], args[1]
        model.rec("vexDeviceMotorVelocitySet", dev, velocity, 0)
        m = model._motor(dev)
        if m:
            m.cmd_velocity = velocity

    def vexDeviceMotorBrakeModeGet(sim, args):
        dev = args[0]
        m = model._motor(dev)
        v = m.brake_mode if m else 0
        model.rec("vexDeviceMotorBrakeModeGet", dev, v, 0)
        return v

    def vexDeviceMotorEncoderUnitsGet(sim, args):
        dev = args[0]
        m = model._motor(dev)
        v = m.enc_units if m else 0
        model.rec("vexDeviceMotorEncoderUnitsGet", dev, v, 0)
        return v

    def vexDeviceMotorGearingGet(sim, args):
        dev = args[0]
        m = model._motor(dev)
        v = m.gear if m else 0
        model.rec("vexDeviceMotorGearingGet", dev, v, 0)
        return v

    def vexDeviceMotorReverseFlagSet(sim, args):
        dev, value = args[0], args[1]
        model.rec("vexDeviceMotorReverseFlagSet", dev, 1 if value else 0, 0)
        m = model._motor(dev)
        if m:
            m.rev_flag = 1 if value else 0

    def vexDeviceMotorReverseFlagGet(sim, args):
        dev = args[0]
        m = model._motor(dev)
        v = m.rev_flag if m else 0
        model.rec("vexDeviceMotorReverseFlagGet", dev, v, 0)
        return 1 if v else 0

    def vexDeviceAbsEncVelocityGet(sim, args):
        dev = args[0]
        m = model._motor(dev)
        v = 0
        if m:
            x = m.velocity
            v = int(x + (0.5 if x >= 0 else -0.5))    # 四舍五入（截断向零）
        model.rec("vexDeviceAbsEncVelocityGet", dev, v, 0)
        return v

    def vexDelay(sim, args):
        ms = args[0] & 0xFFFFFFFF
        model.rec("vexDelay", ms, 0, 0)
        model.advance(float(ms))

    def jhyy_vex_display_puts(sim, args):
        xpos, ypos, ptr = args[0], args[1], args[2]
        model.rec("jhyy_vex_display_puts", xpos, ypos, 0)
        text = sim.str_at.get(ptr, "")
        model.screen.append(text)

    return {
        "vexDeviceGetByIndex": vexDeviceGetByIndex,
        "vexDeviceMotorGearingSet": vexDeviceMotorGearingSet,
        "vexDeviceMotorBrakeModeSet": vexDeviceMotorBrakeModeSet,
        "vexDeviceMotorEncoderUnitsSet": vexDeviceMotorEncoderUnitsSet,
        "vexDeviceMotorVelocitySet": vexDeviceMotorVelocitySet,
        "vexDeviceMotorBrakeModeGet": vexDeviceMotorBrakeModeGet,
        "vexDeviceMotorEncoderUnitsGet": vexDeviceMotorEncoderUnitsGet,
        "vexDeviceMotorGearingGet": vexDeviceMotorGearingGet,
        "vexDeviceMotorReverseFlagSet": vexDeviceMotorReverseFlagSet,
        "vexDeviceMotorReverseFlagGet": vexDeviceMotorReverseFlagGet,
        "vexDeviceAbsEncVelocityGet": vexDeviceAbsEncVelocityGet,
        "vexDelay": vexDelay,
        "jhyy_vex_display_puts": jhyy_vex_display_puts,
    }
