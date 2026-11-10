#!/usr/bin/env bash
# self-test.sh —— **本仓 Python 工具的自测门**
#
# 用法：
#   bash scripts/self-test.sh
#
# 跑四个工具的 `--self-test`：
#   ① astdump.py       —— `jhyy dump` 的 AST 文本解析器
#   ② emit_c.py        —— AST → C（A 路）
#   ③ asm_emit.py      —— AST → ARM 汇编（B 路）
#   ④ binding_surface.py —— 绑定面表（唯一真相源）
#
# ⚠️ 这道门**不需要 VEXcode Pro V5** ⇒ 可以在 stock runner 上跑 ⇒ 是 **CI 门**
#    （验收线 § 6.1）。产物门才是本地门（§ 6.2）。
#
# ⚠️ 每个自测都必须**能红**：它们断言的是**期望的文本**，不是 observed 反推。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"

if [ -z "${PY:-}" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PY=python3
    elif command -v python >/dev/null 2>&1; then
        PY=python
    else
        echo "[self-test] 找不到 python —— 用 PY=<路径> 指一个" >&2
        exit 2
    fi
fi

run() {
    echo "── $1"
    "$PY" "$1" --self-test
}

run "$REPO/spike/day1-emit/astdump.py"
run "$REPO/spike/day1-emit/emit_c.py"
run "$REPO/spike/route-b/asm_emit.py"
run "$REPO/spike/binding/binding_surface.py"

echo "✔ 本仓 Python 工具的自测全过"
