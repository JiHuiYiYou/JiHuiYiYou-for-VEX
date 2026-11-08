#!/usr/bin/env bash
# check-artifacts.sh —— 产物门：重建黄金参考，核对**事实基线里写的哈希**
#
# 这道门是「本地留存 + 可复现脚本 + 一份哈希清单」那套口径的**执行者**：
# 哈希不在脚本里（避免第二份真相），而是**从文档里读** ——
# 事实基线 § 2.1 改了就得对上，否则这道门红。
#
# ⚠️ 需要 **VEXcode Pro V5**（CI 的 stock runner 上没有）⇒
#    这道门是**本地门**；CI 里对应的是 `workflow_dispatch` 手动触发的那一步。
#
# 用法：
#   scripts/check-artifacts.sh [工程目录] [项目名]
#
# 例：
#   scripts/check-artifacts.sh spike/day0-c day0c

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJ_DIR="${1:-spike/day0-c}"
PROJ_NAME="${2:-day0c}"
BASELINE="$REPO_DIR/docs/00-事实基线.md"

[ -f "$BASELINE" ] || { echo "[check-artifacts] 找不到事实基线: $BASELINE" >&2; exit 1; }

# ── 从事实基线 § 2.1 读出期望的 .bin 哈希与大小 ───────────────────────
# 表格行长这样：
#   | `.bin` | `build/day0c.bin` | **2804 B** | `d77341bd…` |
row=$(grep -F '`build/'"$PROJ_NAME"'.bin`' "$BASELINE" | head -1 || true)
[ -n "$row" ] || { echo "[check-artifacts] 事实基线 § 2.1 里没有 $PROJ_NAME.bin 的哈希行" >&2; exit 1; }

EXPECT_SHA=$(printf '%s' "$row" | grep -oE '[0-9a-f]{64}' | head -1)
EXPECT_SIZE=$(printf '%s' "$row" | grep -oE '[0-9]+ *B' | head -1 | tr -d ' B')
[ -n "$EXPECT_SHA" ] || { echo "[check-artifacts] 哈希行里没解析出 SHA256" >&2; exit 1; }
[ -n "$EXPECT_SIZE" ] || { echo "[check-artifacts] 哈希行里没解析出大小" >&2; exit 1; }

echo "[check-artifacts] 事实基线期望: $EXPECT_SHA  ($EXPECT_SIZE B)"

# ── 重建（**从干净状态**）────────────────────────────────────────────────
# ⚠️ 陈旧的中间产物能让坏掉的构建脚本照样"绿" ⇒ 门必须先清干净再重建。
#    （家族规约：改构建脚本后必须从干净状态重建，别拿陈旧产物当通过。）
rm -rf "$REPO_DIR/$PROJ_DIR/build"
"$REPO_DIR/scripts/build-vex.sh" "$PROJ_DIR" "$PROJ_NAME" >/dev/null

BIN="$REPO_DIR/$PROJ_DIR/build/$PROJ_NAME.bin"
[ -f "$BIN" ] || { echo "[check-artifacts] 没产出 $BIN" >&2; exit 1; }

ACTUAL_SHA=$(sha256sum "$BIN" | cut -d' ' -f1)
ACTUAL_SIZE=$(stat -c %s "$BIN")

fail=0
if [ "$ACTUAL_SHA" != "$EXPECT_SHA" ]; then
  echo "[check-artifacts] ❌ .bin 哈希对不上" >&2
  echo "    期望 $EXPECT_SHA" >&2
  echo "    实际 $ACTUAL_SHA" >&2
  fail=1
else
  echo "[check-artifacts] ✔ .bin 哈希一致"
fi

if [ "$ACTUAL_SIZE" != "$EXPECT_SIZE" ]; then
  echo "[check-artifacts] ❌ .bin 大小对不上：期望 $EXPECT_SIZE B，实际 $ACTUAL_SIZE B" >&2
  fail=1
else
  echo "[check-artifacts] ✔ .bin 大小一致（$ACTUAL_SIZE B）"
fi

# ── 五层齐全（验收线 § 3.2 的条件之一）────────────────────────────────
for layer in "build/$PROJ_NAME.elf" "build/$PROJ_NAME.map" "build/$PROJ_NAME.bin"; do
  if [ ! -f "$REPO_DIR/$PROJ_DIR/$layer" ]; then
    echo "[check-artifacts] ❌ 缺层: $layer" >&2
    fail=1
  fi
done
[ -d "$REPO_DIR/$PROJ_DIR/build/src" ] || { echo "[check-artifacts] ❌ 缺 .o 层" >&2; fail=1; }

# ── 头部魔数（事实基线 § 3.1）──────────────────────────────────────────
if [ "$(head -c 4 "$BIN")" = "XVX5" ]; then
  echo "[check-artifacts] ✔ 头部魔数 XVX5"
else
  echo "[check-artifacts] ❌ 头部魔数不是 XVX5" >&2
  fail=1
fi

# ── 入口（事实基线 § 3.2）──────────────────────────────────────────────
ENTRY=$("/c/msys64/ucrt64/bin/arm-none-eabi-readelf" -h "$REPO_DIR/$PROJ_DIR/build/$PROJ_NAME.elf" 2>/dev/null \
        | grep -i "Entry point" | grep -oE '0x[0-9a-f]+' | head -1)
if [ -z "$ENTRY" ]; then
  ENTRY=$("arm-none-eabi-readelf" -h "$REPO_DIR/$PROJ_DIR/build/$PROJ_NAME.elf" 2>/dev/null \
        | grep -i "Entry point" | grep -oE '0x[0-9a-f]+' | head -1)
fi
# readelf 打印的是 0x3800020（不补零），统一成 8 位十六进制再比
ENTRY_NORM=$(printf '0x%08x' "$((ENTRY))" 2>/dev/null || echo "$ENTRY")
if [ "$ENTRY_NORM" = "0x03800020" ]; then
  echo "[check-artifacts] ✔ 入口 0x03800020（vexStartup）"
else
  echo "[check-artifacts] ❌ 入口不是 0x03800020，实际 $ENTRY_NORM" >&2
  fail=1
fi

[ "$fail" -eq 0 ] || exit 1
echo "[check-artifacts] ✔ 全过：产物与事实基线 § 2.1 一致"
