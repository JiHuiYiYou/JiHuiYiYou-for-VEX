#!/usr/bin/env bash
# selftest.sh —— mock 的自测（**证明它能红**）
#
# 三件事：
#   ① **确定性**：同一份源跑两遍 ⇒ 轨迹**逐字节相同**
#      （不成立 ⇒ 差分测试就是在比噪声 ⇒ 门没意义）
#   ② **敏感**：把速度从 50 改成 40 ⇒ 轨迹**必须不同**
#      （不成立 ⇒ mock 根本没在跑程序 ⇒ 门是恒绿的假信号）
#   ③ **判读正确**：cmp.jhyy 的四行结论符合 mock 的模型
#      （MOTOR MOVED / CONFIG OK / REVF FLIP / JHY CMP DONE）
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

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

echo "✔ mock 自测通过：确定性 / 敏感 / 判读"
