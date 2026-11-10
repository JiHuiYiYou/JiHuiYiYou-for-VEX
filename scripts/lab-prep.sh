#!/usr/bin/env bash
# lab-prep.sh —— 出发前的"一条命令"：把上机要用的产物全备齐 + 打印清单
#
# 用法：
#   bash scripts/lab-prep.sh
#
# 做四件事：
#   ① 重建实机探针的 .bin（spike/day0-lab）
#   ② 重建 A 路真产物的 .bin（spike/day1-emit/vex，JHYY 源码经 emitter 编出来的）
#   ③ 把两个 .bin 复制成 program.bin（**直接放进 microSD 卡根目录就能跑**）
#   ④ 打印哈希 + 指向 docs/第1步-上机清单.md
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

echo "=== ③ 哈希 ==="
sha256sum spike/day0-lab/program.bin spike/day1-emit/vex/program.bin | sed 's/^/  /'

cat <<'EOF'

=== ④ 上机清单 ===

  1. microSD 卡（FAT32、根目录清空）插进 Brain
  2. Brain 用 USB 连电脑 → VEXcode → 打开 spike/day0-lab 工程 → Download
     ⇒ 答完 8 题，等屏幕出现 "day0-lab DONE - ANSWERS"，**拍这一张**
  3. 再把 program.bin 复制到 microSD 卡根目录（两个产物任选其一带卡跑）
  4. Brain 屏上出现 "jhyy on vex" ⇒ A 路真机跑通 ✔ 拍一张
  5. 回来把照片给我，剩下我写

  详细版：docs/第1步-上机清单.md
EOF

echo "✔ 产物齐了"
