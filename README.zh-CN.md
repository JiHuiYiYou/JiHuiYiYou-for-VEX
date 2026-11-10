<div align="center">

<div><img src="assets/icon-animated.svg" width="96" alt="JHYY 标志"></div>

<div><img src="assets/jhyy-calligraphy.png" width="220" alt="机会翼游 书法 logo"></div>

### JHYY for VEX —— 给机会翼游（JHYY）加一个嵌入式目标

**把 JHYY 编译到 VEX V5 Brain上。全靠实测，不靠猜。**

[![第 0 步](https://img.shields.io/badge/%E7%AC%AC0%E6%AD%A5-%E8%A7%84%E6%A0%BC%E5%AE%8C%E6%88%90-00d4aa)](docs/%E7%AC%AC0%E6%AD%A5-%E9%AA%8C%E6%94%B6%E7%BA%BF.md)
[![规格书](https://img.shields.io/badge/%E8%A7%84%E6%A0%BC%E4%B9%A6-%E5%8D%95%E4%B8%80%E7%9C%9F%E7%9B%B8%E6%BA%90-blue)](docs/00-%E4%BA%8B%E5%AE%9E%E5%9F%BA%E7%BA%BF.md)
[![路线](https://img.shields.io/badge/%E8%B7%AF%E7%BA%BF-B%20%E7%9B%B4%E5%87%BA%20ARM%20%E6%9C%BA%E5%99%A8%E7%A0%81-lightgrey)](#%E8%B7%AF%E7%BA%BF)
[![CI](https://github.com/JiHuiYiYou/JiHuiYiYou-for-VEX/actions/workflows/ci.yml/badge.svg)](https://github.com/JiHuiYiYou/JiHuiYiYou-for-VEX/actions/workflows/ci.yml)
[![协议](https://img.shields.io/badge/%E5%8D%8F%E8%AE%AE-MIT-blue)](LICENSE)
[![English](https://img.shields.io/badge/lang-English-red)](README.md)

[路线](#路线) · [状态](#状态) · [第 0 步实测到了什么](#第-0-步实测到了什么) · [门](#门) · [目录](#目录) · [文档](#文档) · [协议](#协议)

</div>

---

## 这是什么

**JHYY for VEX** 给 [JHYY（机会翼游）](https://github.com/JiHuiYiYou/JiHuiYiYou-compiler) ——
一门自举、静态类型、面向表达式的系统编程语言 —— 加一个**嵌入式目标**：
VEX V5 Brain（ARM，Xilinx Zynq / Cortex-A9）。

目标机器不是难点。难的是 **VEX 这一侧的一切一开始都是未知的**：
产物格式是什么、启动代码替你干了什么、官方 SDK 到底说哪种 ABI、
它的 struct 怎么排、哪些函数能从别的语言安全调用。

所以**第 0 步把这些未知数变成实测值**，写成一份规格书 —— 它同时是真正干活的**黄金参考**。

```
第 0 步（现在）  手写 C 探针 → 产物格式 / 启动链 / ABI / API 面 全部实测
                 ├─ JHYY → C → clang → .bin          （A 路，黄金参考）
                 └─ JHYY → ARM 机器码 → .bin          （B 路，目标）
```

## 路线

目标形态是**路线 B：JHYY 直出 ARM 机器码** —— 不是"转译成 C++"。

**路线 B 换掉的是 clang 的位置，不换 SDK。** `ld` 及以下原样不动：

```
                ┌─ A 路：JHYY → C 源码 → clang ──┐
JHYY 源码 ──────┤                              ├─→ arm-none-eabi-ld
                └─ B 路：JHYY → ARM 机器码 (.o) ┘        │
                                                             ├─ lscript.ld     官方 SDK
                                                             ├─ stdlib_0.lib   官方 SDK
                                                             ├─ libv5rt.a      官方 SDK
                                                             └─ objcopy → .bin 官方 SDK
```

**B = JHYY 出 ARM `.o`，链官方 SDK 出 `.bin`。**

这跟 pros-rs 当年（Rust 出 `.o`、链 libpros）是**同一个路子** ——
区别是**带着实测重走，不带它的沉没成本**。

⇒ 推论也一致：**ABI 必须锁死**（softfp）、**入口必须锁死**（符号名 `main`）、
**绑定面必须锁死**（每个 `extern fn` 逐字对应一个 C 符号）——
链哪份库就认哪份 ABI。这三样锁不住，两路就没法对拍。

## 状态

| | |
|---|---|
| 第 0 步 | ✅ **规格书已完成** —— **八项全部实测**，最后一项在真 Brain 上测得（tick 频率 = **100 Hz**，2026-11-09）；屏显细节（`bOpaque` 语义、文字坐标单位）仍待测 —— 探针已备好：[`spike/day0-lab/`](spike/day0-lab) |
| 第 1–2 步 | 🔶 **emitter 发 C —— 第一个闭环已通**（2026-11-10）：同一个 `hello.jhyy`，主仓编译器那条路与本仓 emitter 那条路，**stdout 逐字相同 + 返回码相同**。下一步：VEX 的 `.bin` + 真机跑 —— [`spike/day1-emit/`](spike/day1-emit) |
| 第 3 步 | ⬜ 对拍 + 规格书收口 |
| B 阶段 | ⬜ JHYY 的 ARM 后端 |

### 谁也没料到的拦路虎

JHYY 的 ABI v4.0.0 把**指针宽度锁死 64 位**，四个目标全是 amd64 ——
**JHYY 现在没有 ARM 目标**。而 `V5_DeviceT` 是 **4 字节**的 C 指针。

⇒ ARM 目标必须**先把指针宽度定成 4 字节**。不定，连 `extern fn` 都对不上。
这是 B 阶段的第一块硬骨头 —— 写进规格书，免得有人用最贵的方式发现它。

## 第 0 步实测到了什么

下面每一条都是本机实测（编译 / 反汇编 / `readelf` / `nm`）——**零 JHYY 变量**。
凡未实测的一律标「待测」，不写推测值。

- **产物格式不需要额外转换器** —— SDK 的 `objcopy` 直出最终格式。
  头 32 字节是 `XVX5` + 版本 1，入口紧跟其后在 `0x03800020`。
- **启动链完全闭合**：清 `.bss` → stdlib 版本校验 → newlib impure data →
  `__libc_init_array` → `vexMain` → `__libc_fini_array`。
- **用户的 `main` 是一个 task，不是主线程** —— SDK 用 `vexTaskAdd(main, 2, "MAIN")`
  把它注册进 VEXos 调度器 ⇒ **B 路必须发射一个不带修饰的 `main` 符号**。
- **ABI 锁定 softfp** —— 我们的 ELF 与 `libv5rt.a` 都没有 `Tag_ABI_VFP_args` 标签。
- **目标是 ARM 态、4 字节定长** ⇒ 后端不必做 Thumb-2 变长编码。
- **API 两层**：C++ `vex::`（1404 个 mangled 符号，刻意不碰）与**纯 C `vex*()`** ——
  后者 JHYY 的 `extern fn` 直接绑，**零胶水层**。
- **struct 布局实测**：packed 与非 packed 都有。整个纯 C API 里**只有一个**按值传的 struct
  （`V5_DeviceVisionRgb`，≤4 B ⇒ 寄存器传参），其余一律指针传递。
- **内存预算**：堆 1 MB、栈 14 KB —— 递归深度是硬约束。

## 门

门清单只有一处：[`docs/第0步-验收线.md` § 6](docs/%E7%AC%AC0%E6%AD%A5-%E9%AA%8C%E6%94%B6%E7%BA%BF.md)。

| 门 | 在哪跑 | 管什么 |
|---|---|---|
| 文档门 | CI | 链接 / `§` 引用 / **验收线不许超前于事实基线** / 裸路径 |
| 文档门自测 | CI | **证明那道门能红** —— 故意把文档弄坏，断言每道检查都抓到了 |
| Shell 门 | CI | `bash -n` + `shellcheck` |
| 产物门 | **本地**（需 VEXcode Pro V5） | 重建黄金参考，核对规格书里记的哈希 / 大小 / 魔数 / 入口 |

```bash
python scripts/check-docs.py              # 文档门
python scripts/check-docs.py --self-test  # 文档门自测
scripts/check-artifacts.sh spike/day0-c day0c      # 产物门（黄金参考）
scripts/check-artifacts.sh spike/day0-lab day0lab  # 产物门（实机探针）
```

> 产物门是**本地门**：GitHub 的 stock runner 上没有 VEXcode Pro V5 ——
> 一个永远绿的 CI 门比没有门更糟。

## 目录

```
jhyy-for-vex/
├── docs/
│   ├── 00-事实基线.md        # ★ 事实单一真相源（Day 0 实测）
│   └── 第0步-验收线.md       # ★ 验收标准 + 拆解 + 门清单
├── scripts/
│   ├── build-vex.sh          # 命令行构建 VEX 工程（不依赖 VEXcode GUI）
│   ├── measure-abi.sh        # 量 struct 布局 / 传参约定
│   ├── check-docs.py         # 文档门（含自测 --self-test）
│   ├── check-artifacts.sh    # 产物门（重建 + 核对哈希清单）
│   └── parse-lab-log.py      # 实机日志 → 规格书里的观测记录
├── spike/
│   ├── day0-c/               # Day 0 探针：手写 C，零 JHYY 变量
│   │   ├── include/jhyy_vex.h # ★ JHYY 绑定面（逐字对应的 extern fn 清单）
│   │   └── src/jhyy_vex.c     #   非变参屏显封装（变参只发生在 C 内部）
│   ├── day0-lab/             # 实机测量探针（把只能上硬件测的五件事一次测掉）
│   │                          # —— 真正的 VEXcode 工程：GUI 里打开就能下载
│   │                          # —— 结果由它自己写进 SD 卡
│   └── day0-abi/             # ABI 测量探针（布局 + 寄存器约定）
├── .github/
│   ├── workflows/ci.yml
│   ├── ISSUE_TEMPLATE/
│   └── pull_request_template.md
├── assets/                   # 家族 logo（与编译器仓 / IDE 仓同款）
└── CONTRIBUTING.md · SECURITY.md · CODE_OF_CONDUCT.md · LICENSE
```

## 文档

| | |
|---|---|
| [`docs/00-事实基线.md`](docs/00-%E4%BA%8B%E5%AE%9E%E5%9F%BA%E7%BA%BF.md) | 事实基线 —— 所有实测数字与平台事实只写在这里，别处只引用不复述 |
| [`docs/第0步-验收线.md`](docs/%E7%AC%AC0%E6%AD%A5-%E9%AA%8C%E6%94%B6%E7%BA%BF.md) | 验收标准、拆解、门清单 |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 怎么构建、跑哪些门、规矩 |
| [`SECURITY.md`](SECURITY.md) | 再分发约束 —— **发布产物前先读** |
| [`CHANGELOG.md`](CHANGELOG.md) | 改了什么 —— 本仓不发版，全部记在这里 |
| [JHYY 编译器主仓](https://github.com/JiHuiYiYou/JiHuiYiYou-compiler) | 语言、规范，以及本项目要对齐的 ABI |
| [机会翼游官网](https://jihuiyiyou.github.io/JiHuiYiYou-website/vex/) | 家族网站 |

## 协议

源码：**MIT** —— 见 [LICENSE](LICENSE)。

⚠️ **产物是另一回事。** 这里产出的 `.bin` / ELF 链了官方 VEX SDK 的 `libv5rt.a`，
里面是 **VEX 专有代码**，受 restrictive redistribution EULA 约束。
在那件事拍板之前（见规格书的待决事项），**不要发布产物**。
本仓**不**分发 SDK 本身。

## 参与

见 [CONTRIBUTING.md](CONTRIBUTING.md)。一句话版：事实先写下来、探针不许长成产品、
**不改 JHYY 主仓** —— 主仓只管语言，**VEX 这套目标支持由本仓自己养**
（永久旁路：只读一份 pin 住的主仓、影子构建、不回灌。口径见验收线 § 3.4）。
