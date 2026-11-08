# Contributing to JiHuiYiYou-for-VEX

这个仓是 JHYY 的 **VEX 嵌入式目标探索仓**。产出是**实测值与规格书**，不是产品代码。

三条比什么都重要的规矩，先看这三条：

1. **事实先写下来再动手** —— 平台事实一律进 `docs/00-事实基线.md`，别写进代码注释里。
2. **第 0 步的产出是知识，不是代码** —— emitter 是探针，不许长成产品
   （`docs/第0步-验收线.md` § 3.1）。
3. **不直接改 JHYY 主仓** —— 本仓实验、拿到实测，回主仓落地，单独评审
   （`docs/第0步-验收线.md` § 3.4）。

---

## 门（gates）

门清单只有一处：[`docs/第0步-验收线.md`](docs/第0步-验收线.md) **§ 6**。
CI 里的每个步骤都对应其中一条；**没有门守着的清单 = 下一个漂移源**。

### CI 门（stock runner 上真的能跑的）

| 门 | 命令 | 管什么 |
|---|---|---|
| 文档门 | `python scripts/check-docs.py` | 链接能落地 · `§ N` 引用能落地 · **验收线不超前于事实基线** · 裸路径能落地 |
| 文档门自测 | `python scripts/check-docs.py --self-test` | **证明上面那道门能红** —— 注入故障，断言每道检查都抓到了 |
| Shell 门 | `bash -n scripts/*.sh` + `shellcheck -x scripts/*.sh` | 脚本语法与常见坑 |

### 本地门（需要 VEXcode Pro V5 ⇒ CI 上跑不了）

| 门 | 命令 | 管什么 |
|---|---|---|
| 产物门 | `scripts/check-artifacts.sh spike/day0-c day0c` | 重建黄金参考，核对**事实基线 § 2.1 里写的哈希 / 大小 / 入口 / 魔数** |

> ⚠️ **产物门是本地门，别假装它每次 PR 都在跑。**
> GitHub 的 stock runner 上没有 VEXcode Pro V5 ⇒ 一道永远绿的 CI 门比没有门更糟。
> CI 里只留了一个**手动触发**的入口（`workflow_dispatch` + 自托管 runner 标签 `vexcode`）。
>
> 哈希不在脚本里，而是**从事实基线 § 2.1 读出来** —— 避免第二份真相。
> 改了产物 ⇒ 改事实基线 § 2.1 ⇒ 跑一遍产物门。

---

## 开发环境

| 需要 | 说明 |
|---|---|
| Windows 10 + MSYS2 bash | `C:\msys64\usr\bin\bash.exe` |
| **VEXcode Pro V5** | 装在 `C:\Program Files (x86)\VEX Robotics\VEXcode Pro V5` —— 产物门与 ABI 测量都需要它 |
| ARM binutils | `C:\msys64\ucrt64\bin\arm-none-eabi-{objdump,readelf,nm}.exe`（`pacman -S mingw-w64-ucrt-x86_64-arm-none-eabi-binutils`） |
| Python 3 | 文档门用 |

> ⚠️ **MSYS2 自带的 `objdump` 是 x86-only**，对 VEX 产物会报
> `can't disassemble for architecture UNKNOWN!` ⇒ 反汇编必须用 `arm-none-eabi-objdump`。

### 常用命令

```bash
# 构建黄金参考
scripts/build-vex.sh spike/day0-c day0c

# 产物门（重建 + 核对事实基线 § 2.1）
scripts/check-artifacts.sh spike/day0-c day0c

# 量 struct 布局与传参约定
scripts/measure-abi.sh

# 文档门 + 自测
python scripts/check-docs.py
python scripts/check-docs.py --self-test
```

---

## 提 PR 的规矩

- **一个 PR 一件事。** 描述里如果需要"并且"，那大概是两个 PR。
- **改了实测值 ⇒ 事实基线 § 2.1 的哈希清单也要更新**，并跑一遍产物门。
- **改了绑定面**（`extern fn` 的名字 / 签名）⇒ 说明 A 路与 B 路会怎么一起改 ——
  绑定面是**两路共用的**，改一边就是改两边。
- **验收线不许超前于事实基线** —— 文档门会盯这条。勾 ✅ 之前先确认那个 § 里真有内容。
- 没跑的门**要在 PR 里写出来** —— 没跑的门就是没过的门。

## 报告不一致

见 [issue 模板](.github/ISSUE_TEMPLATE/bug_report.yml)。关键是**带上实测**：
本仓的价值全在实测值上。

## 安全问题

**不要开公开 issue。** 见 [SECURITY.md](SECURITY.md)。

## 再分发（重要）

本仓的**产物**（`.bin` / ELF）链了 VEX 官方 SDK 的 `libv5rt.a` ⇒ **含 VEX 专有代码**。
官方 SDK 有 restrictive redistribution EULA。

⇒ 在 [`docs/00-事实基线.md`](docs/00-事实基线.md) § 14 拍板之前，
**不要把产物传进公开 repo 或公开渠道**。
本仓的源码是 MIT（见 [LICENSE](LICENSE)），但**源码与产物是两件事**。

## 行为准则

见 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

## 许可

源码 MIT（[LICENSE](LICENSE)）。产物另议 —— 见上面「再分发」。
