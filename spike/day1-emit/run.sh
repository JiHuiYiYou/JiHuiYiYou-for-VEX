#!/usr/bin/env bash
# run.sh —— Day 1–2 的闭环：JHYY → dump → C → gcc → 跑，并与**主仓编译器行为对拍**
#
# 用法：
#   bash spike/day1-emit/run.sh [源文件.jhyy]
#
# 两条路，同一个源：
#   尺子：主仓编译器  jhyy run prog.jhyy          （JHYY → IL → .s → gcc → .exe）
#   被测：本仓 emitter  dump → C → gcc → .exe      （JHYY → AST → C → gcc → .exe）
# ⇒ 两边 stdout 必须**逐字相同**。
#
# ⚠️ 主仓**一行都不用改**（永久旁路，见验收线 § 3.4）：emitter 只吃
# `jhyy dump` 的文本输出。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

# 主仓的编译器（pin 住的 commit 见验收线 § 3.4.2）
JHY_ROOT="${JHY_ROOT:-/c/Users/liuzhen/Desktop/coding/JiHuiYiYou}"
JHY="$JHY_ROOT/compiler/build/bin/jhyy.exe"
PY="${PY:-C:/Users/liuzhen/miniconda3/python.exe}"

SRC="${1:-$HERE/hello.jhyy}"
NAME="$(basename "$SRC" .jhyy)"
OUT="$HERE/build"
mkdir -p "$OUT"

if [ ! -x "$JHY" ]; then
    echo "[day1-emit] 找不到主仓编译器：$JHY" >&2
    echo "              用 JHY_ROOT=<主仓路径> 指定" >&2
    exit 2
fi

echo "[day1-emit] 源：$SRC"

# ① AST（主仓的 jhyy dump）
"$JHY" dump "$SRC" > "$OUT/$NAME.ast"

# ② C（��仓 emitter）
"$PY" "$HERE/emit_c.py" "$OUT/$NAME.ast" --target host -o "$OUT/$NAME.c"

# ③ 编 + 跑（被测那条路）
gcc -Wall -Wextra -o "$OUT/$NAME.emit.exe" "$OUT/$NAME.c"

# ④ 尺子（主仓编译器那条路；进度行走 stderr ⇒ 丢掉它）
#
# ⚠️ `jhyy run` 会把 .s / .exe 写在**源文件旁边** ⇒ 先把源复制进 build/ 再跑，
#    免得污染仓库。
# ⚠️ **进程的返回码也是可观测行为** ⇒ 两条路都要比，
#    而且 `set -e` 不能让"程序返回非 0"变成脚本失败（那是程序的返回值，不是门失败）。
cp "$SRC" "$OUT/$NAME.jhyy"
set +e
"$OUT/$NAME.emit.exe" > "$OUT/$NAME.emit.out"; EMIT_RC=$?
"$JHY" run "$OUT/$NAME.jhyy" 2>/dev/null > "$OUT/$NAME.ref.out"; REF_RC=$?
set -e

# ⑤ 对拍：stdout **逐字** + 返回码 **相等**
echo "[day1-emit] --- emitter 这条路 --- (rc=$EMIT_RC)"
cat "$OUT/$NAME.emit.out"
echo "[day1-emit] --- 主仓编译器那条路 --- (rc=$REF_RC)"
cat "$OUT/$NAME.ref.out"

fail=0
if ! diff -u "$OUT/$NAME.ref.out" "$OUT/$NAME.emit.out" > "$OUT/$NAME.diff"; then
    echo "❌ stdout 不一致：diff 见 $OUT/$NAME.diff" >&2
    fail=1
fi
if [ "$EMIT_RC" != "$REF_RC" ]; then
    echo "❌ 返回码不一致：emitter=$EMIT_RC  主仓=$REF_RC" >&2
    fail=1
fi
[ "$fail" -eq 0 ] || exit 1
echo "✔ 对拍通过：stdout **逐字相同** + 返回码相同（$EMIT_RC）"
