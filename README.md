# JiHuiYiYou-for-VEX

**让 [JHYY](https://github.com/JiHuiYiYou/JiHuiYiYou-compiler) 直接跑在 VEX V5 Brain 上。**

JHYY 是一门自研语言，有一个自举的编译器、一套自研后端（x86-64）。
本项目给它加一个**嵌入式目标**：VEX V5 Brain（ARM，Xilinx Zynq / Cortex-A9）。

[![Day 0](https://img.shields.io/badge/Day%200-%E5%B7%B2%E5%AE%8C%E6%88%90-00d4aa)](docs/%E7%AC%AC0%E6%AD%A5-%E9%AA%8C%E6%94%B6%E7%BA%BF.md)
[![规格书](https://img.shields.io/badge/%E8%A7%84%E6%A0%BC%E4%B9%A6-%E5%8D%95%E4%B8%80%E7%9C%9F%E7%9B%B8%E6%BA%90-blue)](docs/00-%E4%BA%8B%E5%AE%9E%E5%9F%BA%E7%BA%BF.md)
[![路线](https://img.shields.io/badge/%E8%B7%AF%E7%BA%BF-B%20%E7%9B%B4%E5%87%BA%20ARM%20%E6%9C%BA%E5%99%A8%E7%A0%81-lightgrey)](#%E8%B7%AF%E7%BA%BF)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![CI](https://github.com/JiHuiYiYou/JiHuiYiYou-for-VEX/actions/workflows/ci.yml/badge.svg)](https://github.com/JiHuiYiYou/JiHuiYiYou-for-VEX/actions/workflows/ci.yml)

> **本仓是探索仓，产出是知识不是代码。**
> 第 0 步的交付物是一份把 VEX 侧未知数**全部变成实测值**的规格书 ＋ 一份可逐层对拍的黄金参考。
> 门清单见 [`docs/第0步-验收线.md`](docs/第0步-验收线.md) § 6；
> 参与方式见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

---

## 路线

**目标形态是 B：JHYY 直出 ARM 机器码**（不是"转译成 C++"）。

但第 0 步先花几天做一件更基础的事：**把 VEX 侧的未知数全部变成实测值**，
写成一份规格书 —— 它同时也是 B 阶段的黄金参考。

```
第 0 步（现在）  手写 C 探针 → 产物格式 / 启动链 / ABI / API 面 全部实测
                 ├─ JHYY → C → clang → .bin          （A 路，黄金参考）
                 └─ JHYY → ARM 机器码 → .bin          （B 路，目标）
```

### 路线 B 的边界：换掉的是 **clang**，不是 SDK

"JHYY 直出 ARM 机器码"容易被读成"完全脱离 SDK"。**不是。**
B 替换的是 **clang 的位置**，`ld` 及以下**原样不动**：

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

这恰好就是 pros-rs 当年的**同构**（Rust 出 `.o`、链 libpros），
区别是**你带着实测重走，不带它的沉没成本**。

⇒ 推论也一致：**ABI 必须锁死**（softfp）、**入口必须锁死**（符号名 `main`）、
**绑定面必须锁死**（每个 `extern fn` 逐字对应一个 C 符号）——
链哪份库就认哪份 ABI，这三样锁不住，两路就没法对拍。

---

## 现在的状态

| | |
|---|---|
| Day 0 | ✅ **已完成** —— 见 [`docs/00-事实基线.md`](docs/00-事实基线.md) |
| Day 1–2 | ⬜ emitter 发 C（最小子集）+ 最小绑定面 |
| Day 3 | ⬜ 对拍 + 规格书收口 |
| B 阶段 | ⬜ JHYY 的 ARM 后端 |

### Day 0 已经实测到的（摘要，详见事实基线）

- **产物格式不需要额外转换器**：SDK 的 `objcopy` 直出最终格式；
  头 32 字节 `XVX5` + 版本 1，入口钉在 `0x03800020`。
- **启动链完全闭合**：清 `.bss` → stdlib 版本校验 → newlib impure data →
  `__libc_init_array` → `vexMain` → `__libc_fini_array`。
- **用户的 `main` 是一个 task**（`vexTaskAdd(main, 2, "MAIN")`），不是主线程。
  ⇒ **B 路必须发射一个不带修饰的 `main` 符号**。
- **ABI 锁定 softfp**（与 `libv5rt.a` 双向一致）。
- **目标指令集是 ARM 态 4 字节定长** ⇒ 不必做 Thumb-2 变长编码。
- **API 两层**：C++ `vex::`（1404 个 mangled 符号）与**纯 C `vex*()`**
  —— 后者 JHYY 的 `extern fn` 直接绑，**零胶水层**。
- **struct 布局实测**：packed 与非 packed 都有；C API 里**只有一个**按值传的 struct
  （`V5_DeviceVisionRgb`，≤4 B ⇒ 寄存器传参）。
- **JHYY 的硬约束**（ABI v4.0.0 § 6）：不支持变参、不支持 struct 按值跨 FFI；
  且**指针宽度锁死 64 位** ⇒ ARM 目标要先定成 4 字节。
- 内存预算：堆 1 MB / 栈 14 KB。

---

## 门

门清单只有一处：[`docs/第0步-验收线.md`](docs/第0步-验收线.md) **§ 6**。

| 门 | 在哪跑 | 管什么 |
|---|---|---|
| 文档门 | CI | 链接 / `§` 引用 / **验收线不许超前于事实基线** / 裸路径 |
| 文档门自测 | CI | **证明那道门能红** |
| Shell 门 | CI | `bash -n` + `shellcheck` |
| 产物门 | **本地**（需 VEXcode Pro V5） | 重建黄金参考，核对事实基线 § 2.1 的哈希 / 大小 / 魔数 / 入口 |

```bash
python scripts/check-docs.py              # 文档门
python scripts/check-docs.py --self-test  # 文档门自测
scripts/check-artifacts.sh spike/day0-c day0c   # 产物门
```

---

## 目录

```
jhyy-for-vex/
├── docs/
│   ├── 00-事实基线.md        # ★ 事实单一真相源（Day 0 实测）
│   └── 第0步-验收线.md       # ★ 验收标准 + 拆解 + 🔒 写死条款 + 门清单
├── scripts/
│   ├── build-vex.sh          # 命令行构建 VEX 工程（不依赖 VEXcode GUI）
│   ├── measure-abi.sh        # 量 struct 布局 / 传参约定
│   ├── check-docs.py         # 文档门（含自测 --self-test）
│   └── check-artifacts.sh    # 产物门（重建 + 核对事实基线的哈希清单）
├── spike/
│   ├── day0-c/               # Day 0 探针：手写 C，零 JHYY 变量
│   │   ├── include/jhyy_vex.h # ★ JHYY 绑定面（逐字对应的 extern fn 清单）
│   │   └── src/jhyy_vex.c     #   非变参屏显封装（变参只发生在 C 内部）
│   └── day0-abi/             # ABI 测量探针（布局 + 寄存器约定）
├── .github/
│   ├── workflows/ci.yml      # CI 门
│   ├── ISSUE_TEMPLATE/       # issue 模板
│   └── pull_request_template.md
├── CONTRIBUTING.md · SECURITY.md · CODE_OF_CONDUCT.md · LICENSE
```

---

## 规矩

1. **事实先写下来再动手** —— 平台事实一律进 `docs/00-事实基线.md`，别写进代码注释里。
2. **第 0 步的产出是知识，不是代码** —— emitter 是探针，不许长成产品。
   （这条在 [`第0步-验收线.md`](docs/第0步-验收线.md) § 3 里写死了。）
3. **不直接改 JHYY 主仓** —— 本仓实验、拿到实测，再回主仓落地，单独评审。
4. **产物本地留存，不进版本库** —— `.bin` / ELF 含 `libv5rt.a` 的代码（VEX 专有）；
   在 [`00-事实基线.md`](docs/00-事实基线.md) § 14 拍板前不进公开 repo。
   留存靠**本地 + 可复现脚本 + 哈希清单**（§ 2.1）。
5. **验收线不许超前于事实基线** —— 勾 ✅ 之前先确认那个 § 里真有实测值。
   文档门会盯这条。

---

## 参考

- [JHYY 编译器主仓](https://github.com/JiHuiYiYou/JiHuiYiYou-compiler) —— 语言规范 / 编译器 / 门
- VEX V5 SDK（随 VEXcode Pro V5 安装）：`…\VEXcode Pro V5\sdk\vexv5\`
  ⚠️ **SDK 不随本仓分发**（EULA，见 [`SECURITY.md`](SECURITY.md)）。
- [vexide](https://github.com/vexide/vexide) —— Rust 版 VEX V5 运行时，
  本项目的路线参照物（它的三段演化史在 `docs/第0步-验收线.md` 里有引用）。
