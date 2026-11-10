#!/usr/bin/env bash
# selftest.sh —— mock 的自测（**证明它能红**）
#
# 五件事：
#   ① **确定性**：同一份源跑两遍 ⇒ 轨迹**逐字节相同**
#      （不成立 ⇒ 差分测试就是在比噪声 ⇒ 门没意义）
#   ② **敏感**：把速度从 50 改成 40 ⇒ 轨迹**必须不同**
#      （不成立 ⇒ mock 根本没在跑程序 ⇒ 门是恒绿的假信号）
#   ③ **判读正确**：cmp.jhyy 的四行结论符合 mock 的模型
#      （MOTOR MOVED / CONFIG OK / REVF FLIP / JHY CMP DONE）
#   ④ **A 路 vs B 路行为对拍**：两条路都在 PC 上跑 ⇒ 轨迹与屏显**逐字相同**
#   ⑤ **证明 ④ 能红**：把 B 路汇编改回**旧的错误写法** ⇒ 对拍**必须报红**
#
# ④⑤ 是**新增**的 —— 实测在没有它们的时候，B 路藏着两个真 bug
# （`<`/`>` 操作数写反、尾声没还栈帧），静态门完全看不出来。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PY="${PY:-python}"

run() {   # $1 = 源.jhyy  $2 = 输出前缀
    bash "$HERE/run-host.sh" "$1" 2000 >/dev/null 2>&1
    local base
    base="$(basename "$1" .jhyy)"
    cp "$HERE/build/$base.trace" "$2.trace"
    cp "$HERE/build/$base.screen" "$2.screen" 2>/dev/null || true
}

echo "── ① 确定性：同一份源跑两遍 ⇒ 轨迹逐字节相同"
run "$REPO/spike/day3-cmp/cmp.jhyy" "$TMP/a"
run "$REPO/spike/day3-cmp/cmp.jhyy" "$TMP/b"
if cmp -s "$TMP/a.trace" "$TMP/b.trace"; then
    echo "   ✔ 两遍轨迹相同"
else
    echo "   ❌ 两遍轨迹不同 ⇒ mock 不确定 ⇒ 差分测试不成立" >&2
    diff -u "$TMP/a.trace" "$TMP/b.trace" | head -10 >&2
    exit 1
fi

echo "── ② 敏感：速度 50 → 40 ⇒ 轨迹必须不同"
sed 's/vexDeviceMotorVelocitySet(dev, 50)/vexDeviceMotorVelocitySet(dev, 40)/' \
    "$REPO/spike/day3-cmp/cmp.jhyy" > "$TMP/v40.jhyy"
run "$TMP/v40.jhyy" "$TMP/c"
if cmp -s "$TMP/a.trace" "$TMP/c.trace"; then
    echo "   ❌ 改了速度轨迹却一样 ⇒ mock 没在跑程序（恒绿假信号）" >&2
    exit 1
else
    echo "   ✔ 轨迹变了（$(diff "$TMP/a.trace" "$TMP/c.trace" | grep -c '^[<>]') 行不同）"
fi

echo "── ③ 判读：四行结论符合 mock 的模型"
cat > "$TMP/expect.txt" <<'EOF'
MOTOR MOVEDCONFIG OKREVF FLIPJHY CMP DONE
EOF
# ⚠️ Windows 文本模式会把 \n 写成 \r\n ⇒ 两边都去掉 \r 再比
tr -d '\r' < "$TMP/a.screen" > "$TMP/a.screen.n"
tr -d '\r' < "$TMP/expect.txt" > "$TMP/expect.n"
if cmp -s "$TMP/a.screen.n" "$TMP/expect.n"; then
    echo "   ✔ 屏上文字与预期一致"
else
    echo "   ❌ 屏上文字与预期不一致：" >&2
    echo "     实际：$(cat "$TMP/a.screen.n")" >&2
    echo "     预期：$(cat "$TMP/expect.n")" >&2
    exit 1
fi

echo "── ④ A 路 vs B 路：行为对拍（轨迹 + 屏显逐字相同）"
if bash "$HERE/diff-ab.sh" "$REPO/spike/day3-cmp/cmp.jhyy" 2000 > "$TMP/ab.log" 2>&1; then
    grep -E "^✔" "$TMP/ab.log" | sed 's/^/   /'
else
    echo "   ❌ A/B 对拍没过：" >&2
    cat "$TMP/ab.log" >&2
    exit 1
fi

echo "── ⑤ 证明 ④ 能红：把 B 路汇编改回旧的错误写法 ⇒ 对拍必须报红"
#     旧写法 = 比较时把**右操作数**放 r0、**左操作数**放 r1（`cmp r0, r1`
#     于是算成"右 - 左"）⇒ `<` / `>` 全反 ⇒ 这正是实测踩过的那个 bug。
"$PY" - "$HERE/build/cmp.s" "$TMP/cmp-buggy.s" <<'PY'
import sys
src, dst = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8").read()
good = "    mov r1, r0\n    pop {r0}\n"
bad = "    pop {r1}\n"
if good not in text:
    print("   ❌ 生成的汇编里找不到比较块（%r）—— 改法变了，自测要跟着改" % good,
          file=sys.stderr)
    sys.exit(1)
open(dst, "w", encoding="utf-8", newline="\n").write(text.replace(good, bad))
PY
"$PY" "$HERE/run_sim.py" "$TMP/cmp-buggy.s" 2000 > "$TMP/buggy.trace" 2> "$TMP/buggy.screen"
tr -d '\r' < "$TMP/buggy.trace" > "$TMP/buggy.trace.n"
tr -d '\r' < "$TMP/a.trace" > "$TMP/a.trace.n"
tr -d '\r' < "$TMP/buggy.screen" > "$TMP/buggy.screen.n"
tr -d '\r' < "$TMP/a.screen" > "$TMP/a.screen.n"
# ⚠️ **比较写反时，调用轨迹可能一模一样**（还是那 4 次屏显调用），
#    变的是**屏上文字**（MOTOR MOVED → MOTOR NO MOVE、REVF FLIP → REVF SAME）
#    ⇒ 光比轨迹抓不住 ⇒ **必须也比屏显**。
if cmp -s "$TMP/a.trace.n" "$TMP/buggy.trace.n" \
   && cmp -s "$TMP/a.screen.n" "$TMP/buggy.screen.n"; then
    echo "   ❌ 改坏了 B 路，对拍却还是绿的 ⇒ 这道门抓不住 bug（恒绿假信号）" >&2
    exit 1
else
    echo "   ✔ 改坏之后对拍报红（轨迹差 $(diff "$TMP/a.trace.n" "$TMP/buggy.trace.n" | grep -c '^[<>]') 行 /" \
         "屏显差 $(diff "$TMP/a.screen.n" "$TMP/buggy.screen.n" | grep -c '^[<>]') 行）⇒ 这道门抓得住"
fi

echo "✔ mock 自测通过：确定性 / 敏感 / 判读 / A-B 对拍 / 对拍能红"
