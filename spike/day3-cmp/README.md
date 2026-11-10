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
3. 速度 **50 RPM**，转 **500 ms**
4. 读**实测**速度（绝对编码器，RPM）⇒ 判断「电机到底转没转」
5. 读**回**刹车模式（★ **enum 返回** ⇒ r0 高 3 字节未定义 ⇒ **B 路必须掩码 0xff**）
6. 停机
7. 屏显两行

屏显（两条路显示**同样的字**，所以拍照就能比）：

```
(1, 1)   MOTOR MOVED   |   MOTOR DID NOT MOVE
(1, 20)  BRAKE READBACK OK   |   BRAKE READBACK BAD
```

> 「实测速度」用的是**绝对编码器**（`vexDeviceAbsEncVelocityGet`）——
> `vexDeviceMotorVelocityGet` 返回的是**命令值**，不是实测值（别用错）。

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
| 动作 | `vexDeviceMotorVelocitySet` |
| 测量 | `vexDeviceAbsEncVelocityGet` / `vexDeviceMotorBrakeModeGet` |
| 延时 | `vexDelay` |
| 屏显 | `jhyy_vex_display_puts`（**我们的非变参封装**，不是 `vexDisplayPrintf`） |

⚠️ **enum 传参**：JHYY 侧没有 enum ⇒ 传**序号**（`0/1/2`），
C 侧隐式转成 SDK 的 enum。序号表在绑定面表里（`ENUMS`）。
⚠️ **enum 返回**：1 字节 ⇒ `r0` 高 3 字节未定义 ⇒ **B 路掩码 `0xff`**（实测产物里有这条 `and`）。

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
