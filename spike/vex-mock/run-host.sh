#!/usr/bin/env bash
# run-host.sh —— 在 **host** 上跑一个 JHYY 程序（用 mock 顶替 VEX API）
#
# 用法：
#   bash spike/vex-mock/run-host.sh <源.jhyy> [模拟时长ms]
#
# 例：
#   bash spike/vex-mock/run-host.sh spike/day3-cmp/cmp.jhyy 3000
#
# 它做五件事：
#   ① jhyy dump 源.jhyy                    （主仓现成的命令，主仓一行不改）
#   ② emit_c.py --target vex → 生成的主机.c（**逐字**发绑定面表里的精确原型）
#   ③ gcc：生成的 C（-Dmain=jhyy_main）+ mock + runner
#   ④ 跑 ⇒ stdout = **调用轨迹**，stderr = 屏上文字
#   ⑤ 打印轨迹与屏上文字
#
# ★ **这个脚本能替代真机吗？** —— **不能**（B 路是裸机码，host 上跑不了）。
#    它替代的是「同一段逻辑的两种写法」在**没有机器人**时的等价性验证
#    （差分测试：比调用轨迹）。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

JHY_ROOT="${JHY_ROOT:-/c/Users/liuzhen/Desktop/coding/JiHuiYiYou}"
JHY="$JHY_ROOT/compiler/build/bin/jhyy.exe"
PY="${PY:-C:/Users/liuzhen/miniconda3/python.exe}"
CC="${CC:-gcc}"

SRC="${1:-}"
MAXMS="${2:-3000}"
[ -n "$SRC" ] || { echo "[vex-mock] 用法：run-host.sh <源.jhyy> [模拟时长ms]" >&2; exit 2; }
[ -x "$JHY" ] || { echo "[vex-mock] 找不到主仓编译器：$JHY" >&2; exit 2; }

WORK="$HERE/build"
mkdir -p "$WORK"
BASE="$(basename "$SRC" .jhyy)"

# ① AST
"$JHY" dump "$SRC" > "$WORK/$BASE.ast"

# ② 生成 C（VEX 目标 ⇒ 发的是绑定面表里的精确原型）
"$PY" "$REPO/spike/day1-emit/emit_c.py" "$WORK/$BASE.ast" --target vex \
      -o "$WORK/$BASE.c"

# ③ 编（生成的 C 的 main 改名；runner 提供真 main）
"$CC" -c -Dmain=jhyy_main -I "$HERE" "$WORK/$BASE.c" -o "$WORK/$BASE.o"
"$CC" -c -I "$HERE" "$HERE/vex_mock.c" -o "$WORK/vex_mock.o"
"$CC" -c -I "$HERE" "$HERE/runner.c"  -o "$WORK/runner.o"
"$CC" "$WORK/$BASE.o" "$WORK/vex_mock.o" "$WORK/runner.o" -o "$WORK/$BASE.exe"

# ④⑤ 跑
"$WORK/$BASE.exe" "$MAXMS" > "$WORK/$BASE.trace" 2> "$WORK/$BASE.screen"

echo "[vex-mock] 轨迹（$WORK/$BASE.trace）："
cat "$WORK/$BASE.trace"
echo
echo "[vex-mock] 屏上文字（$WORK/$BASE.screen）："
cat "$WORK/$BASE.screen"
