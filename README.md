# jhyy-for-vex

**让 [JHYY](https://github.com/JiHuiYiYou/JiHuiYiYou) 直接跑在 VEX V5 Brain 上。**

JHYY 是一门自研语言，有一个自举的编译器、一套自研后端（x86-64）。
本项目给它加一个**嵌入式目标**：VEX V5 Brain（ARM，Xilinx Zynq / Cortex-A9）。

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
- **ABI 锁定 softfp**（与 `libv5rt.a` 双向一致）。
- **目标指令集是 ARM 态 4 字节定长** ⇒ 不必做 Thumb-2 变长编码。
- **API 两层**：C++ `vex::`（1404 个 mangled 符号）与**纯 C `vex*()`**
  —— 后者 JHYY 的 `extern fn` 直接绑，**零胶水层**。
- 内存预算：堆 1 MB / 栈 14 KB。

---

## 目录

```
jhyy-for-vex/
├── docs/
│   ├── 00-事实基线.md        # ★ 事实单一真相源（Day 0 实测）
│   └── 第0步-验收线.md       # ★ 验收标准 + 拆解 + 🔒 写死条款
├── scripts/
│   └── build-vex.sh          # 命令行构建 VEX 工程（不依赖 VEXcode GUI）
└── spike/
    └── day0-c/               # Day 0 探针：手写 C，零 JHYY 变量
```

---

## 规矩

1. **事实先写下来再动手** —— 平台事实一律进 `docs/00-事实基线.md`，别写进代码注释里。
2. **第 0 步的产出是知识，不是代码** —— emitter 是探针，不许长成产品。
   （这条在 [`第0步-验收线.md`](docs/第0步-验收线.md) § 3 里写死了。）
3. **不直接改 JHYY 主仓** —— 本仓实验、拿到实测，再回主仓落地，单独评审。

---

## 参考

- VEX V5 SDK（随 VEXcode Pro V5 安装）：`…\VEXcode Pro V5\sdk\vexv5\`
- [vexide](https://github.com/vexide/vexide) —— Rust 版 VEX V5 运行时，
  本项目的路线参照物（它的三段演化史在 `docs/第0步-验收线.md` 里有引用）。
# JiHuiYiYou-for-VEX
