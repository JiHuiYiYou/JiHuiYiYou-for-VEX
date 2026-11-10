# day1-emit —— Day 1–2 的 C emitter（探针）

> **一句话**：把一份 JHYY 源码变成 C，再和主仓编译器**行为对拍**。
> 主仓**一行都不用改**（永久旁路，见 [`../../docs/第0步-验收线.md`](../../docs/%E7%AC%AC0%E6%AD%A5-%E9%AA%8C%E6%94%B6%E7%BA%BF.md) § 3.4）。

## 为什么走这条路

Day 1–2 的目标（验收线 § 2）：**emitter 发 C，不发 C++** —— 输出 C 就没有 name mangling，
`extern fn` 一一对应，少一整类问题。

而主仓**已经有** `jhyy dump`（AST 树打印，一行一个节点、字段 `key=value` ⇒ 机器可解析）⇒
**emitter 只需要吃那份文本** ⇒ 不碰主仓、不进主仓的构建、不动主仓的 ABI。

## 跑一遍

```bash
bash spike/day1-emit/run.sh              # 用 hello.jhyy
bash spike/day1-emit/run.sh 别的.jhyy    # 换一个源
```

它做五件事：

1. `jhyy dump 源.jhyy` → `build/*.ast`（**主仓的命令**）
2. `emit_c.py` 读 AST → `build/*.c`（**本仓的 emitter**）
3. `gcc -Wall -Wextra` 编 + 跑 → `build/*.emit.out`
4. `jhyy run 源.jhyy` → `build/*.ref.out`（**尺子**：主仓编译器那条路）
5. **对拍**：stdout 逐字 `diff` + 返回码相等 ⇒ 不等就红

> 主仓的进度行走 **stderr** ⇒ `2>/dev/null` 拿到的就是程序自己的输出。
> 源文件会被复制进 `build/` 再跑 —— `jhyy run` 会把 `.s` / `.exe` 写在源旁边，别污染仓库。

## 现在的状态

```
$ bash spike/day1-emit/run.sh
[day1-emit] --- emitter 这条路 --- (rc=7)
i=0
i=1
i=2
sum=7
big=7
[day1-emit] --- 主仓编译器那条路 --- (rc=7)
i=0
i=1
i=2
sum=7
big=7
✔ 对拍通过：stdout **逐字相同** + 返回码相同（7）
```

⇒ **第一个闭环通了**（2026-11-10）：`hello.jhyy` 的两条路行为一致。

## 支持的子集（验收线 § 2 的最小子集）

| 能力 | 状态 |
|---|---|
| 常量（`INT` / `STRING`） | ✔ |
| `let`（**带类型**或可推导） | ✔ `mut` 在 C 侧无对应，忽略 |
| 算术 / 比较 / 逻辑 | ✔ `BINARY` 的 `op` 直接落 C |
| `if` / `while` | ✔ |
| 函数调用（含 `extern fn`） | ✔ |
| `extern fn` 声明 | ✔ VEX 目标**发**原型（= 绑定面 ABI 的检查器）；host 目标**不发**（libc 头文件拥有） |
| 字符串字面量 | ✔ |
| struct 布局 / struct 字面量 / 字段访问 | ✔ |

## 已知的坑（记下来，不在 emitter 里绕过 —— 验收线 § 3.1）

| 坑 | 现象 | 现在的处置 |
|---|---|---|
| `extern fn` 原型重复声明 | host 上 `printf` 与 stdio.h 冲突 ⇒ **conflicting types** | 加 `--extern-decls auto\|emit\|omit`（auto：vex 发、host 不发） |
| `*u8` 映成 `unsigned char *` | 每处调用都带指针类型 warning | 探针里 `*u8` → `char *`（VEX 的 C API 与 printf 的 `%s` 都要 `char *`）；**真正定绑定面时逐个 `extern fn` 按 C 侧签名定**（事实基线 § 9.2） |
| 字段访问的形状 | `p.x` 在 AST 里是 `FIELD` 包一个**带 `field=` 属性的 IDENT** | 已处理（基对象在子节点上） |

## 入口符号

`main_jhyy` → **`main`**。VEX 的 `vexMain` 用 `R_ARM_ABS32 main` 取用户 main 的地址
（事实基线 § 9.3）⇒ 必须是**不带修饰**的 `main`。

## 指针宽度

JHYY 语义锁 64 位，但**这条路不受影响** —— emitter 发的是 C 类型，
宽度由 clang 的 `-target thumbv7` 决定（事实基线 § 8.1 末尾）。

## 下一步

1. ⏳ **烧到 Brain 上跑**（缺一次实验室）：`vex/build/day1vex.bin` 已就绪（2516 B）
2. **子集补齐**：`else` 分支、数组、切片、函数指针（按需要排）
3. **overlay**：C 路完全够用 ⇒ **ARM 后端（B 路）才需要 overlay**（验收线 § 3.4.3 的共享层风险）

## A 路真产物（2026-11-10 已就绪）

`vex_demo.jhyy`（**第一份真 JHYY 源码**：调绑定面在 Brain 屏上出字）
⇒ `build-vex.sh` ⇒ `vex/build/day1vex.bin`（2516 B）

```bash
bash spike/day1-emit/build-vex.sh
```

它做五件事：dump → 发 C（`--target vex`）→ **核对生成物与入库那份逐字节相同**（防漂移）
→ 编 VEX 工程 → **核对入口符号 `main` 不带修饰 + 绑定面符号在产物里**。

已核实（事实基线 § 2.1）：

- `jhyy_vex.o` 与黄金参考 `day0-c` 的哈希**完全相同** ⇒
  **A 路与黄金参考调的是同一个绑定面符号**，在**字节层面**坐实 ✓
- 入口符号 `main` 存在且**不带修饰**（VEX 的 `vexMain` 用 `R_ARM_ABS32 main` 取它）✓
- 产物逐字节可复现 ✓

> ⚠️ **还没在 Brain 上跑过**（缺一次实验室）。
> `vex/src/main.c` 是**生成的**（入库是为了 GUI 里打开就能编）⇒
> emitter 一改，`build-vex.sh` 会**红**并告诉你要重新生成 ✓

## 文件

| 文件 | 是什么 |
|---|---|
| `astdump.py` | 解析 `jhyy dump` 的 AST 文本（带 `--self-test`） |
| `emit_c.py` | AST → C（带 `--self-test`） |
| `hello.jhyy` | host 对拍样例：最小子集每样都用一点 |
| `vex_demo.jhyy` | VEX 样例：调绑定面 |
| `run.sh` | host 闭环 + 对拍门 |
| `build-vex.sh` | VEX 产物：dump → C → `.bin` + 符号核对 |
| `vex/` | VEX 工程（makefile / vex/ / 共享绑定面 / 生成的 `src/main.c`） |
