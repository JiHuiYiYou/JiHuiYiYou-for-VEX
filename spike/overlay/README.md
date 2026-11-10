# overlay —— B 路（直出 ARM 机器码）的旁路文件

> **这里放的是"真源"**：本仓自己写的 JHYY 源文件，构建时**叠加**到主仓源码树的
> **影子副本**上编译（主仓工作树一个字都不改）。

## 为什么是 overlay 而不是改主仓

验收线 § 3.4 的契约：**主仓只管语言，VEX 这套目标支持由本仓自己养**（永久旁路）。
overlay 是这个契约的**具体形状**：

```
主仓（只读，pin 在 be6d37b7）
        │  复制
        ▼
   影子树 .tmp/overlay-build/compiler/
        ▲  叠加 spike/overlay/*.jhyy
        │
   本仓 spike/overlay/      ← 真源
```

## 怎么用

```bash
bash scripts/overlay-build.sh
```

它做四件事：① 核对主仓 HEAD 与 pin；② 复制主仓的 `Makefile` + `compiler/` 到影子树；
③ 把本目录的 `*.jhyy` 覆盖进影子树的 `compiler/src0/`；④ 在影子树里 `make`。

⇒ **主仓工作树全程不动**；主仓前进了它会**提醒**（pin 对不上就喊）。

## 现在有什么

**还没有** —— 这一步只是**打通管道**（影子构建能编出一份可用的 `jhyy.exe`，48 秒）。
ARM 后端（`abi_arm_v5.jhyy` + `codegen_arm_v5*.jhyy`）还没写。

## 写 ARM 后端时的已知坑（验收线 § 3.4.3）

「指针宽度 8→4」**落在共享层**，不是纯加法：

| 文件 | 位置 | 要动什么 |
|---|---|---|
| 主仓 `compiler/src0/ir.jhyy` | `qbe_type_of()` | `KIND_POINTER/REF/CAP/SLICE` 一律 `QBE_L()`（8 字节）⇒ 得能按目标给 4 字节 |
| 主仓 `compiler/src0/types.jhyy` | `size_of()` | `KIND_REF` → `8` ⇒ 同上 |
| 主仓的 ABI 文档 `jhyy-abi-v4.0.0.md` | 类型表 / 锁定项 | 文档也要跟上 |

⇒ 两条路（验收线 § 3.4.3 写过）：
* **(A)** pin 死主仓版本、不再跟进上游（诚实省心，但实测会停在旧版编译器上）
* **(B)** 把那两处做成**极小且显式**的 patch 放进 overlay，并写进同步清单

⇒ 无论哪条，**overlay 里的文件都是本仓的真源** ⇒ 主仓不动 ⇒ 契约不变 ✓
