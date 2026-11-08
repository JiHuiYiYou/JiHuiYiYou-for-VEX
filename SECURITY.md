# Security Policy

`JiHuiYiYou-for-VEX` 是 JHYY 的 **VEX 嵌入式目标探索仓** —— 一个研究性质的技术探针，
由一个人维护。

这个仓的"安全"问题**不是常规意义上的漏洞**，而是三类具体的事：

1. **产物里含 VEX 专有代码**（再分发风险）
2. **构建脚本在本机跑**（装 SDK、跑 linker）
3. **文档里的实测值被当成事实引用**（正确性风险）

---

## 1. 再分发风险 —— 最高优先级

本仓产出的 `.bin` / ELF **链了 VEX 官方 SDK 的 `libv5rt.a`**，
里面是 **VEX 专有代码**。官方 SDK 有 restrictive redistribution EULA。

**如果你拿到本仓的产物并打算再分发（公开发布、上传、做成附件、打包给别人）：**

> **先别发。** 先看 [`docs/00-事实基线.md`](docs/00-事实基线.md) § 14「SDK 再分发」，
> 那里记录了当前的判断与待决点。

本仓**自己的源码**是 MIT，可以自由用。**产物不是** —— 这是两件事。

## 2. 不要开公开 issue

对于上面那类（EULA / 再分发）的问题：

**不要开公开 issue。** 用
[私有 advisory 表单](https://github.com/JiHuiYiYou/JiHuiYiYou-for-VEX/security/advisories/new)，
或者直接邮件 **15901598712@163.com**。

公开 issue 会被索引、镜像、缓存 —— 报告本身可能先于修复扩散出去。

## 3. 报告一个安全问题

用[私有 advisory 表单](https://github.com/JiHuiYiYou/JiHuiYiYou-for-VEX/security/advisories/new)，
或邮件 **15901598712@163.com**。请写清：

- 你做了什么
- 为什么这是问题
- 影响面（谁会受影响、影响什么）
- 你建议怎么处理

**会怎么处理：**确认收到 → 评估 → 修复或说明为什么不修 → 披露。
没有承诺时限 —— 这是个单人维护的探索仓。

## 4. 什么**不**算安全问题

| 例子 | 去哪儿 |
|---|---|
| 文档里的实测值算错了 | 普通 issue（带实测）—— 那是**正确性**问题，不是安全问题 |
| 构建脚本在你机器上跑不起来 | 普通 issue |
| JHYY 语言本身的行为 | [编译器主仓](https://github.com/JiHuiYiYou/JiHuiYiYou-compiler) |
| VEX 固件/硬件的漏洞 | 找 VEX —— 跟我们无关 |

## 5. 本仓跑的东西

`scripts/build-vex.sh` 会**调用本机装的 VEXcode Pro V5 工具链**（clang / ld / objcopy）
和一个**你自己放进 `spike/` 的 SDK 目录**。
它不下载任何东西、不联网、不写 SDK 目录以外的系统位置。

`scripts/measure-abi.sh` 只编译一个 `.c` 到临时目录，用完删掉。

> 装 SDK 本身请走 VEX 的官方渠道，别从本仓或任何镜像拿 ——
> 本仓**不**分发 SDK。
