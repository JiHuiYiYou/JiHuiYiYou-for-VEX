#!/usr/bin/env bash
# build-vex.sh —— A 路真产物：**JHYY → AST → C → clang → .bin**
#
# 用法：
#   bash spike/day1-emit/build-vex.sh
#
# 五步：
#   ① jhyy dump vex_demo.jhyy            （主仓现成的命令，主仓一行不改）
#   ② emit_c.py --target vex → vex/src/main.c
#   ③ **核对**生成的 main.c 与仓库里那份**逐字节相同**（防漂移）
#   ④ 用 VEX 工程的 makefile 编 → build/day1vex.bin
#   ⑤ 核对入口符号：**main 不带修饰**（VEX 的 vexMain 用 R_ARM_ABS32 main 取它）
#
# ⚠️ 产物含 `libv5rt.a` 的代码（VEX 专有）⇒ **不进版本库**（.gitignore），
#    留存口径 = 本地 + 可复现脚本 + 哈希清单（事实基线 § 2.1）。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

JHY_ROOT="${JHY_ROOT:-/c/Users/liuzhen/Desktop/coding/JiHuiYiYou}"
JHY="$JHY_ROOT/compiler/build/bin/jhyy.exe"
PY="${PY:-C:/Users/liuzhen/miniconda3/python.exe}"
SRC="$HERE/vex_demo.jhyy"
PROJ="$HERE/vex"
NAME="day1vex"

if [ ! -x "$JHY" ]; then
    echo "[day1-emit] 找不到主仓编译器：$JHY" >&2
    exit 2
fi

mkdir -p "$HERE/build"

# ① AST
"$JHY" dump "$SRC" > "$HERE/build/vex_demo.ast"

# ② C（VEX 目标：发 extern 原型 ⇒ 顺带当绑定面 ABI 的检查器）
"$PY" "$HERE/emit_c.py" "$HERE/build/vex_demo.ast" --target vex -o "$HERE/build/main.c"

# ③ 核对：入库那份 `vex/src/main.c` 必须与刚生成的**逐字节相同**
#    （不一致 = emitter 变了但没重新生成 ⇒ 门要红）
if [ -f "$PROJ/src/main.c" ] && ! cmp -s "$HERE/build/main.c" "$PROJ/src/main.c"; then
    echo "[day1-emit] ❌ 生成的 main.c 与入库那份不同 —— emitter 变了？" >&2
    diff -u "$PROJ/src/main.c" "$HERE/build/main.c" | head -40 >&2
    echo "[day1-emit]    确认无误后：cp build/main.c vex/src/main.c && git add" >&2
    exit 1
fi
cp "$HERE/build/main.c" "$PROJ/src/main.c"

# ④ 编（VEX 工程）
bash "$REPO/scripts/build-vex.sh" "$PROJ" "$NAME"

# ⑤ 入口符号：必须是**不带修饰**的 main
OBJDUMP="/c/msys64/ucrt64/bin/arm-none-eabi-objdump.exe"
if "$OBJDUMP" -t "$PROJ/build/$NAME.elf" | grep -qE "\bmain$"; then
    echo "✔ 入口符号 main 存在且不带修饰（VEX 的 vexMain 用 R_ARM_ABS32 main 取它）"
else
    echo "❌ 入口符号 main 不对 —— VEX 跑不起来" >&2
    "$OBJDUMP" -t "$PROJ/build/$NAME.elf" | grep -w main >&2
    exit 1
fi

# 绑定面符号在不在
if "$OBJDUMP" -t "$PROJ/build/$NAME.elf" | grep -q "jhyy_vex_display_puts"; then
    echo "✔ 绑定面符号 jhyy_vex_display_puts 在产物里"
else
    echo "❌ 产物里没有 jhyy_vex_display_puts" >&2
    exit 1
fi

echo "[day1-emit] 产物：$PROJ/build/$NAME.bin"
sha256sum "$PROJ/build/$NAME.bin"
