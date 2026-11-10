#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make-v5code.py —— 生成三个 Day 3 对照工程的 `.v5code`（VEXcode Pro 的工程文件）

**为什么需要它**：`.v5code` 才是 VEXcode Pro GUI 认的工程入口 ——
双击它就打开工程，点 Download 就烧录。没有它，用户只能在 GUI 里
"Open Folder" 挑目录（麻烦、还容易挑错）。

**为什么要生成而不手写**：文件清单得跟磁盘上的实际文件一致
⇒ 扫描目录生成 ⇒ 不会出现"清单里有、磁盘上没有"（GUI 打开时报错）。

用法：
    python spike/day3-cmp/make-v5code.py           # 生成
    python spike/day3-cmp/make-v5code.py --check   # 只核对（入库那份是否已过期）

★ 为什么 `isExpertModeRC: true`：
    VEXcode 的 Robot Configuration 面板会**自动创建**
    `include/robot-config.h` + `src/robot-config.cpp`（实测：它的
    `updateRobotConfigFiles()` 在文件不存在时直接 newFile）。
    ⇒ 那个面板在我们工程里没有意义（不配任何设备），开着只是引入漂移。
    `isExpertModeRC: true` ⇒ 工具栏上那个按钮**被禁用** ⇒ 面板打不开
    ⇒ VEXcode 不会碰我们的工程目录。

    （就算它被创建了也不要紧：`--gc-section` + `-ffunction-sections`
    会把没人调用的空 `vexcodeInit` 丢掉 ⇒ 产物逐字节不变。实测见
    事实基线 § 2.1 的备注。）
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# (工程名 = make 的 PROJECT / 产物名, 目录名, 描述)
PROJECTS = [
    ("cmp-a", "vex-a",
     "JHYY for VEX - Day 3: route A (JHYY -> C -> clang)"),
    ("cmp-b", "vex-b",
     "JHYY for VEX - Day 3: route B (JHYY -> ARM machine code)"),
    ("cmp-cpp", "vex-cpp",
     "JHYY for VEX - Day 3: C++ reference (vex:: classes)"),
]

# 与 VEXcode Pro 2023-09 版一致（day0-lab 那份实测能开能烧）
VERSION = "23.09.1216"
# 与本机安装的 SDK 完全一致 ⇒ 打开时**不会**弹"升级老工程"
SDK = "20220726_10_00_00"
ICON = "USER921x.bmp"


def scan_files(proj_dir):
    """列出工程里所有文件（相对路径，排序），再列出目录。"""
    files, dirs = [], []
    for sub in ("include", "src", "vex"):
        d = os.path.join(proj_dir, sub)
        if not os.path.isdir(d):
            continue
        dirs.append(sub)
        for name in sorted(os.listdir(d)):
            p = os.path.join(d, name)
            if os.path.isfile(p):
                files.append("%s/%s" % (sub, name))
    if os.path.isfile(os.path.join(proj_dir, "makefile")):
        files.append("makefile")
    files.sort()
    return files, dirs


def build(title, proj_dir, description):
    files, dirs = scan_files(proj_dir)
    entries = [{"name": n, "type": "File", "specialType": ""} for n in files]
    entries += [{"name": d, "type": "Directory"} for d in dirs]
    return {
        "title": title,
        "description": description,
        "icon": ICON,
        "version": VERSION,
        "sdk": SDK,
        "language": "cpp",
        "competition": False,
        "files": entries,
        "device": {"slot": 8, "uid": "276-4810", "options": {}},
        "isExpertMode": True,
        "isExpertModeRC": True,
        "isVexFileImport": False,
        "robotconfig": [],
        "neverUpdate": None,
    }


def dumps(obj):
    # 与 day0-lab.v5code 同样的紧凑写法（无空格、单行）
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def main():
    check = "--check" in sys.argv
    bad = 0
    for title, dirname, description in PROJECTS:
        proj_dir = os.path.join(HERE, dirname)
        if not os.path.isdir(proj_dir):
            print("找不到工程目录：%s" % proj_dir, file=sys.stderr)
            return 2
        text = dumps(build(title, proj_dir, description))
        path = os.path.join(proj_dir, "%s.v5code" % title)
        if check:
            if not os.path.isfile(path):
                print("❌ %s 不存在（跑一次 make-v5code.py）" % path, file=sys.stderr)
                bad = 1
                continue
            old = open(path, encoding="utf-8").read()
            if old != text:
                print("❌ %s 与生成结果不一致 —— 工程文件清单过期了" % path,
                      file=sys.stderr)
                print("   跑：python spike/day3-cmp/make-v5code.py", file=sys.stderr)
                bad = 1
            else:
                print("✔ %s 与生成结果一致" % os.path.relpath(path, HERE))
        else:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            print("✔ 生成 %s" % os.path.relpath(path, HERE))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
