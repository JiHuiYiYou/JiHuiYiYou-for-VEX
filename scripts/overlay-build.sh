#!/usr/bin/env bash
# overlay-build.sh —— **影子构建**：主仓源码树（只读）→ 复制 → 叠加本仓 overlay → 编
#
# 用法：
#   bash scripts/overlay-build.sh
#
# 为什么要有这一层（验收线 § 3.4「永久旁路」）：
#   * 主仓工作树**全程不动** —— 只读一份源码树，复制到影子目录里再改；
#   * 本仓的 `spike/overlay/*.jhyy` 是**真源**，影子树只是构建产物；
#   * pin 住的主仓 commit（§ 3.4.2）⇒ 实测结论对应哪版编译器，说得清。
#
# ⚠️ 这一步现在只是**打通管道**（overlay 还是空的）——
#    ARM 后端（B 路）落地后，这里就是它的构建入口。
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JHY_ROOT="${JHY_ROOT:-/c/Users/liuzhen/Desktop/coding/JiHuiYiYou}"
PIN="be6d37b72afe77f88e32500361cdefd979d1653b"      # ← 验收线 § 3.4.2
WORK="$REPO/.tmp/overlay-build"
OVERLAY="$REPO/spike/overlay"

if [ ! -d "$JHY_ROOT/compiler" ]; then
    echo "[overlay] 找不到主仓：$JHY_ROOT（用 JHY_ROOT=<路径> 指定）" >&2
    exit 2
fi

# ① pin 检查 —— 主仓走了就提醒（不失败：主仓前进不是错，但同步是义务）
HEAD="$(git -C "$JHY_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
if [ "$HEAD" != "$PIN" ]; then
    echo "[overlay] ⚠️ 主仓 HEAD=$HEAD，pin=$PIN" >&2
    echo "[overlay]    ⇒ 主仓已经前进 ⇒ 该按验收线 § 3.4.2 的同步义务过一遍了" >&2
else
    echo "[overlay] ✔ 主仓在 pin 上：$PIN"
fi

# ② 复制（**只读**主仓 —— 主仓工作树一个字都不改）
rm -rf "$WORK"
mkdir -p "$WORK"
cp "$JHY_ROOT/Makefile" "$WORK/"
cp -r "$JHY_ROOT/compiler" "$WORK/compiler"
echo "[overlay] 影子树：$WORK"

# ③ 叠加本仓的 overlay（同名覆盖）
if compgen -G "$OVERLAY/*.jhyy" > /dev/null; then
    for f in "$OVERLAY"/*.jhyy; do
        cp "$f" "$WORK/compiler/src0/$(basename "$f")"
        echo "[overlay] 叠加：$(basename "$f")"
    done
else
    echo "[overlay] （overlay 目录还没有 .jhyy —— 管道阶段）"
fi

# ④ 编
#
# ⚠️ `STRICT_TOOLCHAIN=0`：主仓那道 **W-117 工具链漂移检查**是给**发布构建**用的
#    （"重新编出的 jhyy.exe 必须与提交进仓那份逐字节相同"）。
#    影子构建**不是发布**（主仓的 CI 也是这么传的）⇒ 不受它管。
#    ⚠️ 代价：影子构建出的二进制会随**本机 gcc 版本**漂移
#    ⇒ 实测结论要写清是"**源码 commit X + 本机 gcc Y**"（见验收线 § 3.4.2）。
echo "[overlay] 开始构建（自举：jhyy.exe 自己编 src0）……"
( cd "$WORK" && make STRICT_TOOLCHAIN=0 ) > "$WORK/build.log" 2>&1 || {
    echo "[overlay] ❌ 构建失败，日志尾：" >&2
    tail -30 "$WORK/build.log" >&2
    exit 1
}

BIN="$WORK/compiler/build/bin/jhyy.exe"
[ -x "$BIN" ] || { echo "[overlay] ❌ 没产出 jhyy.exe" >&2; exit 1; }

echo "[overlay] ✔ 构建成功：$BIN"
echo "[overlay]   （自举闭环的产物哈希见 $WORK/compiler/build/）"
sha256sum "$BIN" | sed 's/^/    /'
echo "[overlay] 影子树留在 $WORK（可删）"
