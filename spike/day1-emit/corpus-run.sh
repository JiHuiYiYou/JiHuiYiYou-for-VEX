#!/usr/bin/env bash
# corpus-run.sh —— 语料对拍门：corpus/ 里**每一份** .jhyy 都跑两条路，逐字比
#
# 用法：
#   bash spike/day1-emit/corpus-run.sh
#
# 为什么要有语料：单个样例只能证明"那一个程序能过"；
# 语料把覆盖面变成**可度量**的 —— 加一个特性 ⇒ 加一个语料 ⇒ 门立刻知道它有没有被覆盖。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
CORPUS="$HERE/corpus"
OUT="$HERE/build/corpus"

JHY_ROOT="${JHY_ROOT:-/c/Users/liuzhen/Desktop/coding/JiHuiYiYou}"
JHY="$JHY_ROOT/compiler/build/bin/jhyy.exe"
PY="${PY:-C:/Users/liuzhen/miniconda3/python.exe}"

if [ ! -x "$JHY" ]; then
    echo "[corpus] 找不到主仓编译器：$JHY" >&2
    exit 2
fi
mkdir -p "$OUT"

pass=0
fail=0
failed=()

for src in "$CORPUS"/*.jhyy; do
    name="$(basename "$src" .jhyy)"

    # ① AST ② C ③ 编 + 跑
    "$JHY" dump "$src" > "$OUT/$name.ast"
    if ! "$PY" "$HERE/emit_c.py" "$OUT/$name.ast" --target host -o "$OUT/$name.c"; then
        echo "[corpus] ❌ $name：emitter 报错"
        fail=$((fail + 1)); failed+=("$name"); continue
    fi
    if ! gcc -Wall -Wextra -o "$OUT/$name.emit.exe" "$OUT/$name.c"; then
        echo "[corpus] ❌ $name：生成的 C 编不过"
        fail=$((fail + 1)); failed+=("$name"); continue
    fi
    set +e
    "$OUT/$name.emit.exe" > "$OUT/$name.emit.out" 2>"$OUT/$name.emit.err"; EMIT_RC=$?
    cp "$src" "$OUT/$name.jhyy"
    "$JHY" run "$OUT/$name.jhyy" 2>/dev/null > "$OUT/$name.ref.out"; REF_RC=$?
    set -e

    if ! diff -u "$OUT/$name.ref.out" "$OUT/$name.emit.out" > "$OUT/$name.diff"; then
        echo "[corpus] ❌ $name：stdout 不一致"
        head -20 "$OUT/$name.diff"
        fail=$((fail + 1)); failed+=("$name"); continue
    fi
    if [ "$EMIT_RC" != "$REF_RC" ]; then
        echo "[corpus] ❌ $name：返回码不一致（emitter=$EMIT_RC 主仓=$REF_RC）"
        fail=$((fail + 1)); failed+=("$name"); continue
    fi

    echo "[corpus] ✔ $name（rc=$EMIT_RC）"
    pass=$((pass + 1))
done

echo "[corpus] 通过 $pass / 失败 $fail"
if [ "$fail" -ne 0 ]; then
    echo "[corpus] 失败的：${failed[*]}" >&2
    exit 1
fi
