#!/usr/bin/env bash
# lab-prep.sh —— 出发前的"一条命令"：把上机要用的产物全备齐 + 打印清单
#
# 用法：
#   bash scripts/lab-prep.sh
#
# 做五件事：
#   ① 重建实机探针的 .bin（spike/day0-lab）
#   ② 重建 A 路真产物的 .bin（spike/day1-emit/vex，JHYY 源码经 emitter 编出来的）
#   ③ 重建 B 路真产物的 .bin（spike/route-b/vex，同一份源码但直出机器码）
#   ④ 重建 Day 3 行为对照的**三份** .bin（A 路 / B 路 / C++ 参考）
#   ⑤ 把 .bin 复制成 program.bin（**直接放进 microSD 卡根目录就能跑**）+ 打印哈希
#
# ⚠️ 产物含 VEX 专有代码（libv5rt.a）⇒ **不进版本库**（.gitignore），
#    留存口径 = 本地 + 可复现脚本 + 哈希清单（事实基线 § 2.1）。
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

echo "=== ① 实机探针（补最后几条：答案 + 反转标志 + SD 写入）==="
bash scripts/build-vex.sh spike/day0-lab day0lab >/dev/null
cp spike/day0-lab/build/day0lab.bin spike/day0-lab/program.bin
echo "  ✔ spike/day0-lab/program.bin  ($(stat -c %s spike/day0-lab/program.bin) B)"

echo "=== ② A 路真产物（真 JHYY 源码 → C → clang）==="
bash spike/day1-emit/build-vex.sh >/dev/null
cp spike/day1-emit/vex/build/day1vex.bin spike/day1-emit/vex/program.bin
echo "  ✔ spike/day1-emit/vex/program.bin  ($(stat -c %s spike/day1-emit/vex/program.bin) B)"

echo "=== ③ B 路真产物（同一份源码 → ARM 汇编 → clang）==="
bash spike/route-b/build-vex.sh >/dev/null
cp spike/route-b/vex/build/routebvex.bin spike/route-b/vex/program.bin
echo "  ✔ spike/route-b/vex/program.bin  ($(stat -c %s spike/route-b/vex/program.bin) B)"

echo "=== ④ Day 3 行为对照的三份（A 路 / B 路 / C++ 参考）==="
bash spike/day3-cmp/build-all.sh >/dev/null
cp spike/day3-cmp/vex-a/build/cmp-a.bin     spike/day3-cmp/vex-a/program.bin
cp spike/day3-cmp/vex-b/build/cmp-b.bin     spike/day3-cmp/vex-b/program.bin
cp spike/day3-cmp/vex-cpp/build/cmp-cpp.bin spike/day3-cmp/vex-cpp/program.bin
echo "  ✔ spike/day3-cmp/vex-a/program.bin     ($(stat -c %s spike/day3-cmp/vex-a/program.bin) B)"
echo "  ✔ spike/day3-cmp/vex-b/program.bin     ($(stat -c %s spike/day3-cmp/vex-b/program.bin) B)"
echo "  ✔ spike/day3-cmp/vex-cpp/program.bin   ($(stat -c %s spike/day3-cmp/vex-cpp/program.bin) B)"

echo "=== ⑤ 哈希 ==="
sha256sum \
    spike/day0-lab/program.bin \
    spike/day1-emit/vex/program.bin \
    spike/route-b/vex/program.bin \
    spike/day3-cmp/vex-a/program.bin \
    spike/day3-cmp/vex-b/program.bin \
    spike/day3-cmp/vex-cpp/program.bin | sed 's/^/  /'

cat <<'EOF'

=== ⑥ 上机清单（详见 Task.md）===

  1. Brain 用 USB 连电脑
  2. **先把电机插到 PORT1**（先插，再烧 —— 插晚了测不到"电机转没转"）
  3. VEXcode → 打开 spike/day3-cmp/vex-a/cmp-a.v5code    → Download → 拍一整屏
  4. VEXcode → 打开 spike/day3-cmp/vex-b/cmp-b.v5code    → Download → 拍一整屏
  5. VEXcode → 打开 spike/day3-cmp/vex-cpp/cmp-cpp.v5code → Download → 拍一整屏
  6. 回来把 3 张照片给我，剩下我写

  三张屏显应当**逐字相同**，都是这四行：
     (1,  1)  MOTOR MOVED  |  MOTOR NO MOVE
     (1, 20)  CONFIG OK    |  CONFIG BAD
     (1, 40)  REVF FLIP    |  REVF SAME | REVF NA
     (1, 60)  JHY CMP DONE

  ❌ 不用买 microSD 卡   ❌ 不用跑 day0-lab 探针   ❌ 不用记任何数字

EOF

echo "✔ 产物齐了"
