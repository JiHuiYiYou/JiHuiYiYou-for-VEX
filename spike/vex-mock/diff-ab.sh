#!/usr/bin/env bash
# diff-ab.sh —— **A 路 vs B 路** 的**行为**对拍（两条路都在 PC 上跑）
#
# 用法：
#   bash spike/vex-mock/diff-ab.sh <源.jhyy> [模拟时长ms]
#
#   A 路：JHYY → AST → **C**  → gcc + **C 版 mock**（`run-host.sh`）
#   B 路：JHYY → AST → **ARM 汇编** → **小解释器** + Python 版 mock（`run-sim.sh`）
#
# 比两样：
#   ① **调用轨迹**（逐行：函数名 + 参数）
#   ② **屏上文字**
#
# ⚠️ **为什么必须有这道门**（实测教训）：
#   静态门（比「调用集合 + 顺序」）**看不见逻辑错误**。
#   实测在写这道门之前，B 路藏着两个真 bug：
#     ① `<` / `>` 的操作数顺序写反 ⇒ `v2 < 0` 被算成 `v2 > 0`
#        ⇒ 真机上 `REVF FLIP` 会打成 `REVF SAME` ⇒ 三份屏显不一致
#     ② 函数尾声没还栈帧 ⇒ 返回地址从局部变量区读 ⇒ **跳到垃圾地址 ⇒ 跑飞**
#   两个都在 PC 上被这道门抓住 ⇒ 不必带上机。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

SRC="${1:-}"
MAXMS="${2:-2000}"
[ -n "$SRC" ] || { echo "[diff-ab] 用法：diff-ab.sh <源.jhyy> [模拟时长ms]" >&2; exit 2; }

BASE="$(basename "$SRC" .jhyy)"

echo "=== ① A 路（JHYY → C → gcc + C 版 mock）==="
bash "$HERE/run-host.sh" "$SRC" "$MAXMS" > /dev/null

echo "=== ② B 路（JHYY → ARM 汇编 → 解释器 + Python 版 mock）==="
bash "$HERE/run-sim.sh" "$SRC" "$MAXMS" > /dev/null

A_TRACE="$HERE/build/$BASE.trace"
A_SCREEN="$HERE/build/$BASE.screen"
B_TRACE="$HERE/build/$BASE.sim.trace"
B_SCREEN="$HERE/build/$BASE.sim.screen"

# ⚠️ Windows 文本模式会把 \n 写成 \r\n ⇒ 两边都去掉 \r 再比
tr -d '\r' < "$A_TRACE" > "$HERE/build/$BASE.a.trace.n"
tr -d '\r' < "$B_TRACE" > "$HERE/build/$BASE.b.trace.n"
tr -d '\r' < "$A_SCREEN" > "$HERE/build/$BASE.a.screen.n"
tr -d '\r' < "$B_SCREEN" > "$HERE/build/$BASE.b.screen.n"

fail=0

if diff -u "$HERE/build/$BASE.a.trace.n" "$HERE/build/$BASE.b.trace.n" \
       > "$HERE/build/$BASE.trace.diff"; then
    echo "✔ 调用轨迹逐行相同（$(wc -l < "$HERE/build/$BASE.a.trace.n") 条）"
else
    echo "❌ **调用轨迹不同** ⇒ 两条路的行为不一致（看下面的 diff）" >&2
    cat "$HERE/build/$BASE.trace.diff" >&2
    fail=1
fi

if diff -u "$HERE/build/$BASE.a.screen.n" "$HERE/build/$BASE.b.screen.n" \
       > "$HERE/build/$BASE.screen.diff"; then
    echo "✔ 屏上文字相同：$(cat "$HERE/build/$BASE.a.screen.n")"
else
    echo "❌ **屏上文字不同** ⇒ 两条路的结论不一样" >&2
    cat "$HERE/build/$BASE.screen.diff" >&2
    fail=1
fi

if [ "$fail" -ne 0 ]; then
    echo "[diff-ab] ❌ A/B 行为对拍没过" >&2
    exit 1
fi
echo "[diff-ab] ✔ A 路与 B 路行为一致（PC 上已验证）"
