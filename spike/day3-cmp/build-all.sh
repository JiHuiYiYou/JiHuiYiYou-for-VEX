#!/usr/bin/env bash
# build-all.sh —— **Day 3 行为对照**：一次编出**三份**产物
#
#   A 路：JHYY → AST → **C**       → clang → cmp-a.bin
#   B 路：JHYY → AST → **ARM 汇编** → clang → cmp-b.bin    ← 与 A 路**同一份源码**
#   C++：  C++（vex:: 类）           → clang → cmp-cpp.bin   ← 同一段逻辑的另一种写法
#
# 静态核对（不用上机能做的，都在下面做完）：
#   ① 三份的**绑定面 `.o` 逐字节相同** ⇒ 三条路调的是同一个符号、同一份语义
#   ② 三份的入口符号 `main` 都不带修饰（VEX 的 vexMain 用 R_ARM_ABS32 main 取它）
#   ③ B 路是 **ARM 态**（4 字节定长），且不产生任何 VFP 指令（softfp）
#   ④ **A 路与 B 路在 `main` 里的调用序列逐条相同** ⇒ 结构层面已经对上
#
# ⚠️ 剩下的是**行为**对照（屏显 + 电机到底转没转）⇒ 必须上机：
#    见 `docs/第1步-上机清单.md` 的「Day 3 行为对照」那三条。
#
# ⚠️ 产物含 `libv5rt.a` 的代码（VEX 专有）⇒ **不进版本库**（.gitignore）。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

JHY_ROOT="${JHY_ROOT:-/c/Users/liuzhen/Desktop/coding/JiHuiYiYou}"
JHY="$JHY_ROOT/compiler/build/bin/jhyy.exe"
PY="${PY:-C:/Users/liuzhen/miniconda3/python.exe}"
SRC="$HERE/cmp.jhyy"
OBJDUMP="/c/msys64/ucrt64/bin/arm-none-eabi-objdump.exe"

if [ ! -x "$JHY" ]; then
    echo "[day3-cmp] 找不到主仓编译器：$JHY" >&2
    exit 2
fi
mkdir -p "$HERE/build"

# ── ① AST（主仓的命令，主仓一行不改）────────────────────────────────────
"$JHY" dump "$SRC" > "$HERE/build/cmp.ast"
echo "[day3-cmp] AST：$HERE/build/cmp.ast"

# ── ② A 路：AST → C ────────────────────────────────────────────────────
"$PY" "$REPO/spike/day1-emit/emit_c.py" "$HERE/build/cmp.ast" --target vex \
      -o "$HERE/build/main.c"

# ── ③ B 路：AST → ARM 汇编 ─────────────────────────────────────────────
"$PY" "$REPO/spike/route-b/asm_emit.py" "$HERE/build/cmp.ast" \
      -o "$HERE/build/main.s"

# ③.5 核对：入库那份（GUI 里打开就能编的那份）必须与刚生成的**逐字节相同**
#     ⇒ emitter 变了但没重新生成 ⇒ 门要红
for pair in "main.c:vex-a/src/main.c" "main.s:vex-b/src/main.s"; do
    gen="$HERE/build/${pair%%:*}"
    dst="$HERE/${pair##*:}"
    if [ -f "$dst" ] && ! cmp -s "$gen" "$dst"; then
        echo "[day3-cmp] ❌ 生成的 ${pair%%:*} 与入库那份不同 —— emitter 改了？" >&2
        diff -u "$dst" "$gen" | head -40 >&2
        echo "[day3-cmp]    确认无误后：cp build/${pair%%:*} ${pair##*:} && git add" >&2
        exit 1
    fi
    cp "$gen" "$dst"
done

# ── ④ 编三份 ────────────────────────────────────────────────────────────
bash "$REPO/scripts/build-vex.sh" "$HERE/vex-a"   "cmp-a"
bash "$REPO/scripts/build-vex.sh" "$HERE/vex-b"   "cmp-b"
bash "$REPO/scripts/build-vex.sh" "$HERE/vex-cpp" "cmp-cpp"

# ── ⑤ 静态核对 ──────────────────────────────────────────────────────────
fail=0

# ⑤.1 绑定面 `.o` 三份逐字节相同
H_A=$(sha256sum "$HERE/vex-a/build/src/jhyy_vex.o"   | cut -d' ' -f1)
H_B=$(sha256sum "$HERE/vex-b/build/src/jhyy_vex.o"   | cut -d' ' -f1)
H_C=$(sha256sum "$HERE/vex-cpp/build/src/jhyy_vex.o" | cut -d' ' -f1)
if [ "$H_A" = "$H_B" ] && [ "$H_B" = "$H_C" ]; then
    echo "✔ 三份的绑定面 .o 逐字节相同 ⇒ 三条路调的是同一个符号"
else
    echo "❌ 绑定面 .o 三份不一致：$H_A / $H_B / $H_C" >&2
    fail=1
fi

# ⑤.2 入口符号 `main` 不带修饰（三份）
for n in cmp-a cmp-b cmp-cpp; do
    p="$HERE/vex-a/build/$n.elf"
    case "$n" in
        cmp-b)   p="$HERE/vex-b/build/$n.elf" ;;
        cmp-cpp) p="$HERE/vex-cpp/build/$n.elf" ;;
    esac
    if "$OBJDUMP" -t "$p" | grep -qE "\bmain$"; then
        echo "✔ $n：入口符号 main 存在且不带修饰"
    else
        echo "❌ $n：入口符号 main 不对 —— VEX 跑不起来" >&2
        fail=1
    fi
done

# ⑤.3 B 路是 ARM 态、且没有 VFP 指令（softfp）
if "$OBJDUMP" -d "$HERE/vex-b/build/cmp-b.elf" | grep -qE "^\s+[0-9a-f]+:\s+e[0-9a-f]{3}\s"; then
    echo "✔ B 路是 ARM 态（4 字节定长指令）"
else
    echo "❌ B 路没看到 ARM 态指令特征" >&2
    fail=1
fi
if "$OBJDUMP" -d "$HERE/vex-b/build/cmp-b.elf" | grep -qiE "\bv[a-z]+\.|\sf64\s|\sf32\s|\tvfp"; then
    echo "⚠️ B 路里出现了浮点/VFP 痕迹 —— softfp 子集不该有" >&2
    fail=1
else
    echo "✔ B 路没有 VFP 指令 ⇒ softfp 天然满足"
fi

# ⑤.4 ★ A 路与 B 路在 `main` 里调的是**同一批函数**、且**顺序**相同
#
# ⚠️ **调用次数可以不同**：clang -Os 会把 if/else 两个分支里**参数形状相同**的
#    调用**尾合并**成一个调用点（先选好字符串指针再统一 bl）——
#    实测：`jhyy_vex_display_puts` 在 A 路只有 2 个调用点，源码里有 4 处。
#    ⇒ 比「调用集合」+「除尾合并项以外的调用顺序」。
main_calls() {
    "$OBJDUMP" -d --disassemble=main "$1" \
        | grep -oE "bl\s+[0-9a-f]+ <[^>]+>" \
        | sed -E 's/.*<([^>]+)>/\1/' || true
}
main_calls "$HERE/vex-a/build/cmp-a.elf" > "$HERE/build/calls-a.txt"
main_calls "$HERE/vex-b/build/cmp-b.elf" > "$HERE/build/calls-b.txt"

sort -u "$HERE/build/calls-a.txt" > "$HERE/build/calls-a.set"
sort -u "$HERE/build/calls-b.txt" > "$HERE/build/calls-b.set"
if diff -u "$HERE/build/calls-a.set" "$HERE/build/calls-b.set" > "$HERE/build/calls-set.diff"; then
    echo "✔ A 路与 B 路调的是同一批函数（$(wc -l < "$HERE/build/calls-a.set") 个）"
else
    echo "❌ A 路与 B 路调的函数集合不同 —— 看 $HERE/build/calls-set.diff" >&2
    cat "$HERE/build/calls-set.diff" >&2
    fail=1
fi

grep -v "jhyy_vex_display_puts" "$HERE/build/calls-a.txt" > "$HERE/build/calls-a.nodisp"
grep -v "jhyy_vex_display_puts" "$HERE/build/calls-b.txt" > "$HERE/build/calls-b.nodisp"
if diff -u "$HERE/build/calls-a.nodisp" "$HERE/build/calls-b.nodisp" > "$HERE/build/calls.diff"; then
    echo "✔ A 路与 B 路的调用顺序逐条相同（除尾合并的屏显调用外）"
else
    echo "❌ A 路与 B 路的调用顺序不同 —— 看 $HERE/build/calls.diff" >&2
    cat "$HERE/build/calls.diff" >&2
    fail=1
fi

# ── ⑥ 三份产物（哈希与事实基线 § 2.1 对）────────────────────────────────
echo
BASELINE="$REPO/docs/00-事实基线.md"
check_bin() {   # $1 = 产物名（cmp-a / cmp-b / cmp-cpp）  $2 = 路径
    local name="$1" path="$2"
    local row sha size
    row=$(grep -F "build/$name.bin" "$BASELINE" | head -1 || true)
    if [ -z "$row" ]; then
        echo "❌ 事实基线 § 2.1 里没有 $name.bin 的哈希行" >&2
        fail=1
        return
    fi
    sha=$(printf '%s' "$row" | grep -oE '[0-9a-f]{64}' | head -1)
    size=$(printf '%s' "$row" | grep -oE '[0-9]+ *B' | head -1 | tr -d ' B')
    local actual_sha actual_size
    actual_sha=$(sha256sum "$path" | cut -d' ' -f1)
    actual_size=$(stat -c%s "$path")
    if [ "$actual_sha" != "$sha" ] || [ "$actual_size" != "$size" ]; then
        echo "❌ $name.bin 与事实基线 § 2.1 不一致" >&2
        echo "    期望 $sha ($size B)" >&2
        echo "    实际 $actual_sha ($actual_size B)" >&2
        fail=1
    else
        printf '✔ %-9s %s  %s B\n' "$name" "$actual_sha" "$actual_size"
    fi
}
check_bin "cmp-a"   "$HERE/vex-a/build/cmp-a.bin"
check_bin "cmp-b"   "$HERE/vex-b/build/cmp-b.bin"
check_bin "cmp-cpp" "$HERE/vex-cpp/build/cmp-cpp.bin"

if [ "$fail" -ne 0 ]; then
    echo "[day3-cmp] ❌ 有核对项没过" >&2
    exit 1
fi
echo "[day3-cmp] ✔ 三份产物都编好了，剩下的**行为**对照要上机（docs/第1步-上机清单.md）"
