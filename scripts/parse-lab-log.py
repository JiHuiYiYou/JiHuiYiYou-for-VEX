#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""parse-lab-log.py —— 把 SD 卡上的 day0lab.txt 变成能贴进规格书的观测记录

用法：
    python scripts/parse-lab-log.py <day0lab.txt>
    python scripts/parse-lab-log.py <day0lab.txt> --session 1     # 取第 1 次
    python scripts/parse-lab-log.py <day0lab.txt> --out record.md

⚠️ 这个脚本**只做转写与机械推导**，不下「未测到的结论」：
    - 缺项 / 超时 ⇒ 明确标「未测到」，不填推测值
    - 推导出来的读法（bOpaque 语义、tick 粒度）标注为「由日志推导」
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SESSION_MARK = "# JHYY-for-VEX day0-lab log"

# (日志键, 中文标签, 怎么读)
FIELDS: list[tuple[str, str, str]] = [
    ("log.path", "日志落在哪个路径", "SD 卡根目录下的文件名"),
    ("log.opened", "日志文件打开成功", "1=成功"),
    ("sd.drive0", "SD 卡在位（drive 0）", "1=在位"),
    ("sd.mount_fr", "挂载结果", "0=FR_OK；其它值见 FatFs FRESULT"),
    ("M1.dev0", "PORT1 有设备", "1=有"),
    ("M1.dev1", "PORT2 有设备", "1=有"),
    ("M1.dev2", "PORT3 有设备", "1=有"),
    ("M1.dev3", "PORT4 有设备", "1=有"),
    ("M1.gear", "齿比 get 回来的值", "1=kMotorGearSet_18"),
    ("M1.brake", "制动模式 get 回来的值", "1=kV5MotorBrakeModeBrake"),
    ("M1.enc", "编码器单位 get 回来的值", "0=kMotorEncoderDegrees"),
    ("M1.pos50.vget", "+50 时速度目标读回", "设 50 读回多少"),
    ("M1.pos50.avel_x10", "+50 时实际速度 × 10", "同上"),
    ("M1.pos50.dir", "+50 时方向读回", "±1"),
    ("M1.pos50.pos_x10", "+50 时位置 × 10（度）", "转 1 秒后的位置"),
    ("M1.neg50.vget", "-50 时速度目标读回", ""),
    ("M1.neg50.dir", "-50 时方向读回", ""),
    ("M1.neg50.pos_x10", "-50 时位置 × 10（度）", "符号应当与 +50 相反"),
    ("M1.revflag_on", "置上反转标志后 get 回来的值", "1=置上了"),
    ("M1.pos50_rev.pos_x10", "置反转标志后 +50 的位置 × 10", "符号应当被翻转"),
    ("M1.revflag_off", "清除后 get 回来的值", "1=还挂着就是没清掉"),
    ("M2.disp_w", "10 个 M 的宽度（像素）", "字体度量"),
    ("M2.disp_h", "10 个 M 的高度（像素）", "字体度量"),
    ("M3.n", "延时循环次数", "每次循环的次数"),
    ("M3.d1_ms", "50 次 vexDelay(1) 总耗时（ms）", "每次真实耗时 = d1/n"),
    ("M3.d0_ms", "50 次 vexDelay(0) 总耗时（ms）", "0 ⇒ 不让出时间片"),
    ("M4.heap_total", "堆总字节", "_heap_end - _heap_start"),
    ("M4.heap_free", "启动时可用堆字节", "_heap_end - 当前 break"),
    ("M4.alloc_ok", "_sbrk(4096) 写入读回", "1=可用"),
    ("M5.cstat", "vexCompetitionStatus 原值", "十六进制"),
    ("controller.present", "控制器在位", "0 ⇒ 提问环节被跳过"),
]

# (日志键, 中文标签, {日志值: 中文})
ANSWERS: list[tuple[str, str, dict[str, str]]] = [
    ("Q1.motor_dir", "电机到底动了吗", {
        "moved": "动了", "did_not_move": "没动",
        "timeout": "（超时未答）", "controller_lost": "（控制器掉线，没答成）"}),
    ("Q2.pix_0_0", "像素 (0,0) 落在哪", {
        "top_left": "左上", "top_right": "右上", "bottom_left": "左下",
        "bottom_right": "右下", "middle_or_other": "中间 / 其它位置",
        "not_seen": "没看到（坐标超出屏幕）",
        "timeout": "（超时未答）", "controller_lost": "（控制器掉线，没答成）"}),
    ("Q3.pix_239_127", "像素 (239,127) 落在哪", {
        "top_left": "左上", "top_right": "右上", "bottom_left": "左下",
        "bottom_right": "右下", "middle_or_other": "中间 / 其它位置",
        "not_seen": "没看到（坐标超出屏幕）",
        "timeout": "（超时未答）", "controller_lost": "（控制器掉线，没答成）"}),
    ("opaque0", "**透明**那一相（原始 API bOpaque=0）：字缝里的块还在吗", {
        "block_visible": "还在（透明）", "block_erased": "没了（不透明）",
        "timeout": "（超时未答）", "controller_lost": "（控制器掉线，没答成）"}),
    ("opaque1", "**不透明**那一相（原始 API bOpaque=1）：字缝里的块还在吗", {
        "block_visible": "还在（透明）", "block_erased": "没了（不透明）",
        "timeout": "（超时未答）", "controller_lost": "（控制器掉线，没答成）"}),
    ("Q6.text_offset", "T52 相对 T00 的偏移方向", {
        "right": "右", "below": "下", "bottom_right": "右下",
        "somewhere_else": "其它方向",
        "timeout": "（超时未答）", "controller_lost": "（控制器掉线，没答成）"}),
    ("Q7.text_unit", "文字起点与 10×10 方块右边缘的关系", {
        "exactly": "正好接上 ⇒ 坐标单位是像素",
        "far_away": "离得很远 ⇒ 坐标单位是字符格",
        "on_the_block": "压在方块上 ⇒ 坐标系与预想不同",
        "somewhere_else": "其它情形",
        "timeout": "（超时未答）", "controller_lost": "（控制器掉线，没答成）"}),
]


def normalize(rec: dict[str, str]) -> dict[str, str]:
    """两代探针的 Q4/Q5 键名不同，**语义槽**相同：

    | 槽 | 老探针（绑定面 bOpaque=0） | 新探针（绑定面改成 1） |
    |---|---|---|
    | `opaque0` = 透明那一相 | `Q4.opaque_binding_surface` | `Q4.opaque_plain_api` |
    | `opaque1` = 不透明那一相 | `Q5.opaque_raw_api` | `Q5.opaque_binding_surface` |

    ⇒ 归一到槽，解析器两代日志都能吃。
    """
    if "Q4.opaque_plain_api" in rec:
        rec.setdefault("opaque0", rec.get("Q4.opaque_plain_api"))
        rec.setdefault("opaque1", rec.get("Q5.opaque_binding_surface"))
    else:
        rec.setdefault("opaque0", rec.get("Q4.opaque_binding_surface"))
        rec.setdefault("opaque1", rec.get("Q5.opaque_raw_api"))
    return rec


def read_sessions(path: Path) -> list[dict[str, str]]:
    """按 SESSION_MARK 把日志切成若干次运行；每次运行 = 一个 key→value 字典。"""
    sessions: list[dict[str, str]] = []
    cur: dict[str, str] = {}

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(SESSION_MARK):
            if cur:
                sessions.append(cur)
            cur = {}
            continue
        if line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        cur[key.strip()] = val.strip()

    if cur:
        sessions.append(normalize(cur))
    return sessions


def derive(rec: dict[str, str]) -> list[str]:
    """**机械推导**（只从日志里已有的值推，不引入推测）。"""
    out: list[str] = []

    q4 = rec.get("opaque0")
    q5 = rec.get("opaque1")
    if q4 == "block_visible" and q5 == "block_erased":
        out.append("**`bOpaque=0` 透、`bOpaque=1` 吃背景**（原始 API 透、绑定面不透）"
                   " ⇒ 绑定面用 `bOpaque=1` ✔（白字黑底，永远可读）。")
    elif q4 == "block_erased" and q5 == "block_visible":
        out.append("**与预期相反**：原始 API 反而不透、绑定面反而透"
                   " ⇒ 绑定面的 `bOpaque` 取值要按实测重定。")
    elif q4 and q5 and "timeout" not in (q4, q5):
        out.append("两个相位的观察结果**相同** ⇒ 单看这一项定不了 `bOpaque` 语义。")

    n = rec.get("M3.n")
    d1 = rec.get("M3.d1_ms")
    d0 = rec.get("M3.d0_ms")
    if n and d1:
        per = int(d1) / int(n)
        if per > 0:
            hz = 1000.0 / per
            out.append(f"`vexDelay(1)` 每次实耗 ≈ **{per:g} ms**（{d1} ms / {n} 次）"
                       f" ⇒ 调度 tick ≈ {per:g} ms ⇒ 消息泵频率 ≈ {hz:.1f} Hz")
        else:
            out.append(f"`vexDelay(1)` 每次实耗 ≈ **0 ms**（{d1} ms / {n} 次）"
                       " ⇒ 计时器或延时没生效")
    if n and d0:
        per0 = int(d0) / int(n)
        out.append(f"`vexDelay(0)` 每次实耗 ≈ **{per0:g} ms**"
                   + (" ⇒ `vexDelay(0)` **不让出**时间片" if per0 == 0 else
                      f" ⇒ `vexDelay(0)` 会让出 ⇒ 调度周期 ≈ {per0:g} ms"))

    vget = rec.get("M1.pos50.vget")
    pos = rec.get("M1.pos50.pos_x10")
    neg = rec.get("M1.neg50.pos_x10")
    rev = rec.get("M1.pos50_rev.pos_x10")

    if pos is not None and neg is not None:
        a, b = int(pos), int(neg)
        same = (a > 0) == (b > 0)
        out.append(f"**符号语义**：+50 转 1 秒位置 `{a / 10:g}` 度，-50 是 `{b / 10:g}` 度"
                   + (" ⇒ 符号**相反**，速度与位置线性对称" if not same
                      else " ⇒ 符号**相同**，速度与位置不是线性关系（要查）"))

    if rev is not None and pos is not None:
        flipped = (int(rev) > 0) != (int(pos) > 0)
        out.append(f"**反转标志**：置上后 +50 的位置是 `{int(rev) / 10:g}` 度"
                   + (" ⇒ 标志**会翻转**位置/方向符号 ⇒ 绑定面必须暴露它"
                      "（左边电机 / 右边电机靠它表达）" if flipped
                      else " ⇒ 标志**没有**翻转位置符号 ⇒ 物理方向另有来源，要查"))

    if vget is not None and pos is not None:
        deg = int(pos) / 10.0
        target = int(vget)
        # 起动有加速度 ⇒ 允许 15% 误差；再给一个 2 度的绝对下限
        tol = max(2.0, 0.15 * abs(target))
        head = (f"速度设 50 → 读回 `vget={target}`，转 1 秒位置 `{deg:g}` 度")
        if abs(deg - target) <= tol:
            out.append(head + " ⇒ 速度单位与 `kMotorEncoderDegrees` **一致（度/秒）**")
        else:
            out.append(head + " ⇒ 速度单位**不是**度/秒，绑定面换算要写清楚")

    free = rec.get("M4.heap_free")
    total = rec.get("M4.heap_total")
    if free and total:
        pct = 100.0 * int(free) / int(total) if int(total) else 0
        out.append(f"启动时堆还剩 **{int(free)} B / {int(total)} B**（{pct:.1f}%）"
                   f" ⇒ JHYY 的 `mem` 预算按这个数算，不是按总量算")

    return out


def self_test() -> int:
    """自测：造一份日志 ⇒ 解析 ⇒ 断言推导结论真的出来了。

    没有自测的工具 = 到了现场才发现坏了。断言必须是**期望值**，
    不是拿 observed 反过来定义 expected。
    """
    import tempfile

    sample = "\n".join([
        SESSION_MARK + "  schema=1",
        "log.path=day0lab.txt", "log.opened=1", "sd.drive0=1", "sd.mount_fr=0",
        "M1.dev0=1", "M1.gear=1", "M1.brake=1", "M1.enc=0",
        "M1.pos50.vget=50", "M1.pos50.avel_x10=487", "M1.pos50.dir=1",
        "M1.pos50.pos_x10=503",
        "M1.neg50.vget=-50", "M1.neg50.avel_x10=-490", "M1.neg50.dir=-1",
        "M1.neg50.pos_x10=-501",
        "M1.revflag_on=1", "M1.pos50_rev.pos_x10=-497", "M1.revflag_off=0",
        "M2.disp_w=80", "M2.disp_h=20",
        "M3.n=50", "M3.d1_ms=150", "M3.d0_ms=0",
        "M4.heap_total=1048576", "M4.heap_free=1046528", "M4.alloc_ok=1",
        "M5.cstat=0x0", "controller.present=1",
        "Q1.motor_dir=moved",
        "Q2.pix_0_0=top_left",
        "Q3.pix_239_127=not_seen",
        "Q4.opaque_plain_api=block_visible",
        "Q5.opaque_binding_surface=block_erased",
        "Q6.text_offset=bottom_right",
        "Q7.text_unit=exactly",
        "done=1",
        "",
    ])

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "day0lab.txt"
        p.write_text(sample, encoding="utf-8", newline="\n")
        sessions = read_sessions(p)
        assert len(sessions) == 1, f"期望切出 1 次运行，实际 {len(sessions)}"
        rec = sessions[0]
        assert rec["M1.pos50.vget"] == "50", rec.get("M1.pos50.vget")
        assert rec["Q4.opaque_plain_api"] == "block_visible"

        d = "\n".join(derive(rec))
        expect = [
            "bOpaque=1", "吃背景",        # 原始透、绑定面不透 ⇒ 1 吃背景
            "3 ms", "333.3 Hz",            # 150/50 = 3 ms
            "不让出",                      # d0 = 0
            "一致（度/秒）",                # 50.3 度 vs 50 度/秒
            "1046528 B",                   # 堆剩余
            "符号**相反**",                # +50 正、-50 负
            "标志**会翻转**",              # 反转标志翻转符号
        ]
        for e in expect:
            assert e in d, f"推导里缺 {e!r}：\n{d}"

        out = Path(td) / "rec.md"
        text, rc = render(p)
        assert rc == 0, rc
        out.write_text(text, encoding="utf-8", newline="\n")
        for e in ["动了", "左上", "度/秒", "bOpaque", "反转标志"]:
            assert e in text, f"输出里缺 {e!r}"

    print("✔ 自测通过：切分 / 解析 / 推导 / 输出都对了")
    return 0


def render(log: Path, session: int = -1) -> tuple[str, int]:
    """把日志渲染成 markdown；返回 (文本, 退出码)。"""
    if not log.exists():
        print(f"找不到日志文件：{log}", file=sys.stderr)
        print("（SD 卡根目录应该有一个 day0lab.txt；没有它说明 SD 写入失败）",
              file=sys.stderr)
        return "", 1

    sessions = read_sessions(log)
    if not sessions:
        print(f"日志里没有可用内容：{log}", file=sys.stderr)
        return "", 1

    idx = session if session >= 0 else len(sessions) - 1
    if idx >= len(sessions):
        print(f"只有 {len(sessions)} 次运行，取不到第 {idx + 1} 次", file=sys.stderr)
        return "", 1
    rec = sessions[idx]

    L: list[str] = []
    L.append(f"<!-- 由 scripts/parse-lab-log.py 从 day0lab.txt 生成；"
             f"共 {len(sessions)} 次运行，取第 {idx + 1} 次 -->")
    L.append("")
    L.append("## 实机观测记录")
    L.append("")
    L.append("### 自动测量")
    L.append("")
    L.append("| 项 | 实测值 | 怎么读 |")
    L.append("|---|---|---|")
    for key, label, how in FIELDS:
        val = rec.get(key)
        mark = "**未测到**" if val is None else f"`{val}`"
        L.append(f"| {label} | {mark} | {how} |")

    L.append("")
    L.append("### 人工观察（控制器按键作答，程序记进日志）")
    L.append("")
    L.append("| 项 | 作答 |")
    L.append("|---|---|")
    for key, label, mapping in ANSWERS:
        val = rec.get(key)
        if val is None:
            shown = "**未测到**"
        else:
            shown = mapping.get(val, f"`{val}`")
        L.append(f"| {label} | {shown} |")

    derived = derive(rec)
    if derived:
        L.append("")
        L.append("### 由日志推导的读法")
        L.append("")
        for d in derived:
            L.append(f"- {d}")

    missing = [label for key, label, _ in FIELDS if key not in rec]
    if missing:
        L.append("")
        L.append(f"> ⚠️ 未测到的项（{len(missing)}）：{'、'.join(missing)}")
        L.append("> —— 验收线不许超前于事实基线，这些项在规格书里保持「待测」。")

    return "\n".join(L) + "\n", 0


def main() -> int:
    ap = argparse.ArgumentParser(description="把 day0lab.txt 转成规格书里的观测记录")
    ap.add_argument("log", type=Path, nargs="?", help="SD 卡上的 day0lab.txt")
    ap.add_argument("--session", type=int, default=-1,
                    help="取第几次运行（默认最后一次；0 起算）")
    ap.add_argument("--out", type=Path, help="写到文件（默认打印到 stdout）")
    ap.add_argument("--self-test", action="store_true",
                    help="造一份假日志自测这个脚本")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.log is None:
        ap.error("需要给出日志文件（或用 --self-test）")

    text, rc = render(args.log, args.session)
    if rc != 0:
        return rc
    if args.out:
        args.out.write_text(text, encoding="utf-8", newline="\n")
        print(f"✔ 已写入 {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
