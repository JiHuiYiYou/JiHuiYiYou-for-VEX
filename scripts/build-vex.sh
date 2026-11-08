#!/usr/bin/env bash
# build-vex.sh — 从命令行构建 VEX V5 工程（不依赖 VEXcode GUI）
#
# 用法：
#   scripts/build-vex.sh <工程目录> [项目名]
#
# 例：
#   scripts/build-vex.sh spike/day0-c day0c
#
# 环境变量：
#   VEXCODE_HOME  VEXcode Pro V5 安装根目录（默认自动探测）
#   VEX_SDK       SDK 目录（默认 $VEXCODE_HOME/sdk）
#
# 产物：<工程目录>/build/<项目名>.{elf,bin,map}
#
# ⚠️ 实测依据见 docs/00-事实基线.md § 2 —— 命令行产物与 VEXcode GUI 产物**逐字节相同**。

set -euo pipefail

PROJ_DIR="${1:?用法: build-vex.sh <工程目录> [项目名]}"
PROJ_NAME="${2:-$(basename "$PWD")}"

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

TOOLCHAIN="$VEXCODE_HOME/toolchain/vexv5/win32"
[ -d "$TOOLCHAIN" ] || { echo "找不到工具链: $TOOLCHAIN" >&2; exit 1; }

export PATH="$TOOLCHAIN/clang/bin:$TOOLCHAIN/gcc/bin:$TOOLCHAIN/tools/bin:$PATH"

# ── 构建 ───────────────────────────────────────────────────────────────
cd "$PROJ_DIR"
echo "[build-vex] 工程: $(pwd)   项目: $PROJ_NAME"
make T="$(cygpath -m "$VEX_SDK" 2>/dev/null || echo "$VEX_SDK")" P="$PROJ_NAME"

BIN="build/$PROJ_NAME.bin"
[ -f "$BIN" ] || { echo "[build-vex] 没产出 $BIN" >&2; exit 1; }

# ── 校验产物格式（§ 3 的事实）────────────────────────────────────────
head -c 4 "$BIN" | grep -q 'XVX5' || { echo "[build-vex] 头部魔数不是 XVX5" >&2; exit 1; }

SIZE=$(stat -c %s "$BIN")
echo "[build-vex] OK  $BIN  ($SIZE B)   魔数 XVX5 ✔   入口 0x03800020（vexStartup）"
echo "[build-vex] 待烧录请复制为 program.bin 放进 microSD 根目录"
