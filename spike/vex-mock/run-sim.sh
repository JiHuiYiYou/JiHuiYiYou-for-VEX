#!/usr/bin/env bash
# run-sim.sh —— 在 **host** 上跑 **B 路**（JHYY → ARM 汇编 → 小解释器）
#
# 用法：
#   bash spike/vex-mock/run-sim.sh <源.jhyy> [模拟时长ms]
#
# 例：
#   bash spike/vex-mock/run-sim.sh spike/day3-cmp/cmp.jhyy 2000
#
# 它做四件事：
#   ① jhyy dump 源.jhyy                    （主仓现成的命令，主仓一行不改）
#   ② asm_emit.py → ARM 汇编（**B 路**的产物）
#   ③ arm_sim.py 解释执行（代替真机）
#   ④ stdout = 调用轨迹，stderr = 屏上文字（**与 C 版 mock 同格式** ⇒ 可直接 diff）
#
# ★ **它补上了 mock 一直缺的那一半**：
#    `run-host.sh` 只能跑 A 路（JHYY → C）⇒ B 路（JHYY → 机器码）的**逻辑**
#    在 PC 上没人验 ⇒ 实测已经因此漏掉过两个真 bug
#    （`<`/`>` 操作数写反、尾声没还栈帧 ⇒ 返回跳到垃圾地址）。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

JHY_ROOT="${JHY_ROOT:-/c/Users/liuzhen/Desktop/coding/JiHuiYiYou}"
JHY="$JHY_ROOT/compiler/build/bin/jhyy.exe"
PY="${PY:-C:/Users/liuzhen/miniconda3/python.exe}"

SRC="${1:-}"
MAXMS="${2:-2000}"
[ -n "$SRC" ] || { echo "[arm-sim] 用法：run-sim.sh <源.jhyy> [模拟时长ms]" >&2; exit 2; }
[ -x "$JHY" ] || { echo "[arm-sim] 找不到主仓编译器：$JHY" >&2; exit 2; }

WORK="$HERE/build"
mkdir -p "$WORK"
BASE="$(basename "$SRC" .jhyy)"

# ① AST
"$JHY" dump "$SRC" > "$WORK/$BASE.ast"

# ② ARM 汇编（B 路）
"$PY" "$REPO/spike/route-b/asm_emit.py" "$WORK/$BASE.ast" -o "$WORK/$BASE.s"

# ③ 解释执行
"$PY" "$HERE/run_sim.py" "$WORK/$BASE.s" "$MAXMS" \
      > "$WORK/$BASE.sim.trace" 2> "$WORK/$BASE.sim.screen"

echo "[arm-sim] 轨迹（$WORK/$BASE.sim.trace）："
cat "$WORK/$BASE.sim.trace"
echo
echo "[arm-sim] 屏上文字（$WORK/$BASE.sim.screen）："
cat "$WORK/$BASE.sim.screen"
