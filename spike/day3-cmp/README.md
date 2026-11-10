# day3-cmp —— **Day 3 行为对照**（同一段逻辑，三种写法）

> **一句话**：把**同一段逻辑**写成三份，烧到同一台 Brain 上，
> 看**屏显**和**电机动作**是不是一样。

## 三份程序

| | 源码 | 怎么编 | 产物 |
|---|---|---|---|
| **A 路** | [`cmp.jhyy`](cmp.jhyy)（JHYY） | → AST → **C** → clang | `vex-a/build/cmp-a.bin`（3020 B） |
| **B 路** | [`cmp.jhyy`](cmp.jhyy)（**同一份** JHYY） | → AST → **ARM 汇编** → clang | `vex-b/build/cmp-b.bin`（3516 B） |
| **C++ 参考** | [`vex-cpp/src/main.cpp`](vex-cpp/src/main.cpp) | C++ / `vex::` 类 → clang | `vex-cpp/build/cmp-cpp.bin`（4368 B） |

★ **A 路与 B 路烧的是同一份 JHYY 源码** ⇒ 两路行为必须一致 ⇒ 这是 **ABI 的行为级检查**。
C++ 参考是**同一段逻辑的另一种写法**（像 7262A 那样用 `vex::` 类）。

## 那段逻辑是什么（七步）

1. 取 PORT1 的电机句柄
2. 配置：齿轮组 **18:1** / 刹车 **Brake** / 编码器单位 **Degrees**
3. **读回**三个配置（刹车 / 编码器单位 / 齿轮组）—— ★ **enum 返回** ⇒ B 路要掩码
4. 速度 **50 RPM**，转 **500 ms**，读**实测**速度（绝对编码器，RPM）
5. **反转标志**实验：置上 → **再读一次** → 再转一次 → 看方向反没反
6. 停机 + 复位标志
7. 屏显**四行**

屏显（三条路显示**同样的字**，所以拍照就能比）：

```
(1,  1)  MOTOR MOVED  |  MOTOR NO MOVE      ← 电机到底转没转
(1, 20)  CONFIG OK    |  CONFIG BAD         ← 三个配置读回来对不对
(1, 40)  REVF FLIP    |  REVF SAME | REVF NA ← 反转标志到底改不改方向
(1, 60)  JHY CMP DONE                         ← 跑到底了（不是卡住）
```

> 「实测速度」用的是**绝对编码器**（`vexDeviceAbsEncVelocityGet`）——
> `vexDeviceMotorVelocityGet` 返回的是**命令值**，不是实测值（别用错）。
>
> `REVF` 那条**顺带补上规格书最后一个缺口**（§ 13.1「还缺的」）：
> 上一轮探针测不出结论，是因为**探针自己有 bug** —— 置完标志又走了一遍
> `config_motor()`，可能把标志清了 ⇒ 读回全同，分不清是「标志被清」还是
> 「标志本来就不影响读回」。这里改成 **先 config → 再置标志 → 再 spin**，
> 并且 **spin 之后再读一次标志** ⇒ 两种情况能分开（标志没置上 ⇒ `REVF NA`）。

## 编一遍

```bash
bash spike/day3-cmp/build-all.sh
```

它做六件事：

1. `jhyy dump cmp.jhyy` → AST（**主仓一行不改**）
2. AST → C（`--target vex`）⇒ `vex-a/src/main.c`
3. AST → ARM 汇编 ⇒ `vex-b/src/main.s`
4. 编三份 VEX 工程
5. **静态核对**（不用上机就能做的）：
   - 三份的**绑定面 `.o` 逐字节相同** ⇒ 三条路调的是同一个符号
   - 三份的入口符号 `main` **不带修饰**（VEX 的 `vexMain` 用 `R_ARM_ABS32 main` 取它）
   - B 路是 **ARM 态**（4 字节定长）且**没有 VFP 指令** ⇒ softfp 天然满足
   - **A 路与 B 路调的是同一批函数、顺序相同**（见下面的「尾合并」）
6. 打印三份产物的哈希与大小

### ⚠️ 「调用次数可以不同」—— clang 的尾合并

实测：源码里 `jhyy_vex_display_puts` 有 **4 处**调用，
A 路（clang `-Os`）的产物里只有 **2 个调用点** —— clang 把 if/else 两个分支里
**参数形状相同**的调用**尾合并**了（先选好字符串指针，再统一 `bl`）：

```asm
    movw r2, =<"MOTOR MOVED">
    b    call
else:
    movw r2, =<"MOTOR DID NOT MOVE">
call:
    mov  r0, #1
    mov  r1, #1
    bl   jhyy_vex_display_puts
```

⇒ 所以门比的是「**调用集合**」+「**除尾合并项以外的调用顺序**」，
不是「调用次数」。B 路（我们的汇编）不做这个优化 ⇒ 4 个调用点。

## 绑定面

三条路调的都是**同一套绑定面**（[唯一真相源](../binding/binding_surface.py)）：

| 用途 | 符号 |
|---|---|
| 取句柄 | `vexDeviceGetByIndex` |
| 配置 | `vexDeviceMotorGearingSet` / `vexDeviceMotorBrakeModeSet` / `vexDeviceMotorEncoderUnitsSet` |
| 配置**读回** | `vexDeviceMotorBrakeModeGet` / `vexDeviceMotorEncoderUnitsGet` / `vexDeviceMotorGearingGet` |
| 动作 | `vexDeviceMotorVelocitySet` |
| 反转标志 | `vexDeviceMotorReverseFlagSet` / `vexDeviceMotorReverseFlagGet` |
| 测量 | `vexDeviceAbsEncVelocityGet` |
| 延时 | `vexDelay` |
| 屏显 | `jhyy_vex_display_puts`（**我们的非变参封装**，不是 `vexDisplayPrintf`） |

⚠️ **enum 传参**：JHYY 侧没有 enum ⇒ 传**序号**（`0/1/2`），
C 侧隐式转成 SDK 的 enum。序号表在绑定面表里（`ENUMS`）。
⚠️ **1 字节返回**（3 个 enum + 1 个 `bool`）⇒ `r0` 高 3 字节未定义 ⇒
**B 路掩码 `0xff`**（实测产物里有 4 条 `and r0, r0, #0xff`）。
⚠️ **bool 实参**（`ReverseFlagSet`）：1 字节 ⇒ B 路传**零扩展的 32 位值**
⇒ callee 按 1 字节读（低字节）或按 4 字节读（整个字）**都对**。

## 上机之后

烧三份，各拍一张 Brain 屏的照片 ⇒ 三张屏显应当**逐字相同**，
且电机都应当转起来（`MOTOR MOVED`）。清单见
[`docs/第1步-上机清单.md`](../../docs/%E7%AC%AC1%E6%AD%A5-%E4%B8%8A%E6%9C%BA%E6%B8%85%E5%8D%95.md)。

## 文件

| 文件 | 是什么 |
|---|---|
| `cmp.jhyy` | **那份** JHYY 源码（A 路与 B 路共用） |
| `vex-a/` | A 路 VEX 工程（`src/main.c` 是**生成的**） |
| `vex-b/` | B 路 VEX 工程（`src/main.s` 是**生成的**；makefile 多一条 `.s` 规则） |
| `vex-cpp/` | C++ 参考工程（`src/main.cpp` 是手写的） |
| `build-all.sh` | 编三份 + 静态核对 |
