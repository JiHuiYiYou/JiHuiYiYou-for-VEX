#!/usr/bin/env bash
# build-vex.sh —— **B 路真产物**：JHYY → AST → **ARM 汇编** → clang → `.bin`
#
# 用法：
#   bash spike/route-b/build-vex.sh
#
# 与 A 路（`spike/day1-emit/build-vex.sh`）的差别只有一步：
#   A 路：AST → **C**   → clang → .o
#   B 路：AST → **汇编** → clang → .o
# ⇒ 两条路的**绑定面 `.o` 必须是同一份字节**（事实基线 § 9.2），
#   差别只在"用户代码那部分怎么来" ⇒ 这才是对拍该比的东西。
#
# ⚠️ 产物含 `libv5rt.a` 的代码（VEX 专有）⇒ **不进版本库**（.gitignore）。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

JHY_ROOT="${JHY_ROOT:-/c/Users/liuzhen/Desktop/coding/JiHuiYiYou}"
JHY="$JHY_ROOT/compiler/build/bin/jhyy.exe"
PY="${PY:-C:/Users/liuzhen/miniconda3/python.exe}"
SRC="$HERE/vex_demo.jhyy"
PROJ="$HERE/vex"
NAME="routebvex"

if [ ! -x "$JHY" ]; then
    echo "[route-b] 找不到主仓编译器：$JHY" >&2
    exit 2
fi
mkdir -p "$HERE/build"

# ① AST（主仓的命令，主仓一行不改）
"$JHY" dump "$SRC" > "$HERE/build/vex_demo.ast"

# ② ARM 汇编
"$PY" "$HERE/asm_emit.py" "$HERE/build/vex_demo.ast" -o "$HERE/build/main.s"

# ③ 核对：入库那份 `vex/src/main.s` 必须与刚生成的**逐字节相同**
if [ -f "$PROJ/src/main.s" ] && ! cmp -s "$HERE/build/main.s" "$PROJ/src/main.s"; then
    echo "[route-b] ❌ 生成的 main.s 与入库那份不同 —— emitter 改了？" >&2
    diff -u "$PROJ/src/main.s" "$HERE/build/main.s" | head -40 >&2
    echo "[route-b]    确认无误后：cp build/main.s vex/src/main.s && git add" >&2
    exit 1
fi
cp "$HERE/build/main.s" "$PROJ/src/main.s"

# ④ 编（VEX 工程：.s 由 clang 汇编，.c 由 clang 编译，一起链）
bash "$REPO/scripts/build-vex.sh" "$PROJ" "$NAME"

# ⑤ 符号核对
OBJDUMP="/c/msys64/ucrt64/bin/arm-none-eabi-objdump.exe"
if "$OBJDUMP" -t "$PROJ/build/$NAME.elf" | grep -qE "\bmain$"; then
    echo "✔ 入口符号 main 存在且不带修饰"
else
    echo "❌ 入口符号 main 不对 —— VEX 跑不起来" >&2
    exit 1
fi
"$OBJDUMP" -t "$PROJ/build/$NAME.elf" | grep -q "jhyy_vex_display_puts" \
    && echo "✔ 绑定面符号 jhyy_vex_display_puts 在产物里" \
    || { echo "❌ 产物里没有 jhyy_vex_display_puts" >&2; exit 1; }

# ⑥ 指令集核对：必须是 **ARM 态**（4 字节定长），不是 Thumb
if "$OBJDUMP" -d "$PROJ/build/$NAME.elf" | grep -qE "^\s+[0-9a-f]+:\s+e[0-9a-f]{3}\s"; then
    echo "✔ 用户代码是 ARM 态（4 字节定长指令）"
else
    echo "⚠️ 没看到 ARM 态指令特征 —— 查一下是不是 Thumb" >&2
fi

echo "[route-b] 产物：$PROJ/build/$NAME.bin"
sha256sum "$PROJ/build/$NAME.bin"
