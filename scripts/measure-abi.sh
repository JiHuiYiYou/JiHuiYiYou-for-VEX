#!/usr/bin/env bash
# measure-abi.sh — 量 VEX C API 的 struct 布局与按值传参约定
#
# 产出（临时目录，不落仓库）：
#   abi_probe.o   —— 测量值以「全局数组长度」编码进符号表
#
# 读法：
#   nm -S abi_probe.o    → m_* 符号的 size 就是测量值
#   objdump -d abi_probe.o → 按值传参/返回的调用点
#
# 环境变量：
#   VEXCODE_HOME  VEXcode Pro V5 安装根目录（默认自动探测）
#   VEX_SDK       SDK 目录（默认 $VEXCODE_HOME/sdk）
#
# ⚠️ 编译选项刻意与 vex/mkenv.mk 的 CFLAGS 一致
#    （尤其 -fshort-enums / -mfloat-abi=softfp / -target thumbv7-none-eabi）
#    —— 选项变了，enum 宽度就会变。

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_DIR/spike/day0-abi/abi_probe.c"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

# ── 定位 VEXcode Pro V5 ────────────────────────────────────────────────
if [ -z "${VEXCODE_HOME:-}" ]; then
  for cand in \
    "/c/Program Files (x86)/VEX Robotics/VEXcode Pro V5" \
    "/c/Program Files/VEX Robotics/VEXcode Pro V5"; do
    if [ -d "$cand/toolchain/vexv5/win32" ]; then VEXCODE_HOME="$cand"; break; fi
  done
fi
: "${VEXCODE_HOME:?找不到 VEXcode Pro V5 —— 用 VEXCODE_HOME=<路径> 指定}"
VEX_SDK="${VEX_SDK:-$VEXCODE_HOME/sdk}"

CLANG="$VEXCODE_HOME/toolchain/vexv5/win32/clang/bin/clang.exe"
OBJDUMP="${ARM_OBJDUMP:-arm-none-eabi-objdump}"
NM="${ARM_NM:-arm-none-eabi-nm}"

# 与 vex/mkenv.mk 的 CFLAGS 对齐（-fshort-enums 会改 enum 宽度！）
FLAGS=(
  -target thumbv7-none-eabi
  -fshort-enums
  -Wno-unknown-attributes
  -U__INT32_TYPE__ -U__UINT32_TYPE__
  "-D__INT32_TYPE__=long" "-D__UINT32_TYPE__=unsigned long"
  -march=armv7-a -mfpu=neon -mfloat-abi=softfp
  -Os -Wall -Werror=return-type -ansi -std=gnu99 -DVexV5
  "-I$VEX_SDK/vexv5/include"
  "-I$VEX_SDK/vexv5/clang/8.0.0/include"
  "-I$VEX_SDK/vexv5/gcc/include"
)

echo "[measure-abi] 编译 $SRC"
"$CLANG" "${FLAGS[@]}" -c "$SRC" -o "$OUT/abi_probe.o"

echo
echo "── 布局测量（符号 size = 测量值）────────────────────────────"
"$NM" -S --size-sort "$OUT/abi_probe.o" | grep -E " m_" | sort -k4

echo
echo "── 按值传参的调用点（probe_call_by_value）────────────────────"
"$OBJDUMP" -d --disassemble=probe_call_by_value "$OUT/abi_probe.o"

echo
echo "── 按值返回的调用点（probe_ret_by_value）──────────────────────"
"$OBJDUMP" -d --disassemble=probe_ret_by_value "$OUT/abi_probe.o"

echo
echo "── enum 实参的传递（probe_call_enum / probe_call_enum_one）─────"
"$OBJDUMP" -d --disassemble=probe_call_enum "$OUT/abi_probe.o"
"$OBJDUMP" -d --disassemble=probe_call_enum_one "$OUT/abi_probe.o"
