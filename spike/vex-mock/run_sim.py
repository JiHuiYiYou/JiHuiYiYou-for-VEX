#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_sim.py —— 用 `arm_sim.py` 解释器跑 emitter 产出的 ARM 汇编（**B 路**）

用法：
    python spike/vex-mock/run_sim.py <main.s> [模拟时长ms]

输出约定与 C 版 mock **完全一致**：
    stdout = 调用轨迹（每行 `序号 函数名 参数…`）
    stderr = 屏上文字

⇒ 两边（A 路跑 C mock / B 路跑解释器）的输出**可以直接 diff**。
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from arm_sim import ArmSim, ProgramExit, SimError      # noqa: E402
from mock_model import MockModel, make_stubs            # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("用法：run_sim.py <main.s> [模拟时长ms]", file=sys.stderr)
        return 2
    asm_path = sys.argv[1]
    max_ms = float(sys.argv[2]) if len(sys.argv) > 2 else 3000.0

    model = MockModel(max_ms)
    sim = ArmSim(make_stubs(model))
    with open(asm_path, encoding="utf-8") as f:
        sim.load(f.read())

    try:
        sim.run("main")
    except ProgramExit:
        # 程序返回（或撞到模拟时钟上限）⇒ 与 C 版 mock 的 `exit(0)` 同义
        pass

    sys.stdout.write(model.trace_text())
    sys.stdout.flush()
    sys.stderr.write(model.screen_text() + "\n")
    sys.stderr.flush()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SimError as e:
        print("[arm-sim] %s" % e, file=sys.stderr)
        sys.exit(1)
