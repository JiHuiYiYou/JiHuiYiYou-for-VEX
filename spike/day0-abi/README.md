# Day 0 ABI 探针（量 struct 布局与传参约定）

> 目的：把 **JHYY 要绑的那些 C 类型** 的真实布局与调用约定**实测**出来，
> 而不是照着头文件猜。
> 结果落在 [`../../docs/00-事实基线.md`](../../docs/00-事实基线.md) § 8.1。

## 它怎么做

`abi_probe.c` 把测量值**编码成全局数组的长度**：

```c
char m_pid_size[sizeof(V5_DeviceMotorPid)];      /* → 符号 size = 12 */
char m_pid_align[__alignof__(V5_DeviceMotorPid)];  /* → 符号 size = 1  */
char m_pid_off_limit[offsetof(V5_DeviceMotorPid, limit)];  /* → 6 */
```

编译期常量在 `.o` 里没有字面量，但数组长度会进**符号表** ⇒ `nm -S` 能直接读回来。
比 `printf` 可靠：不需要实机，结果可被脚本复核。

同一份文件里还放了几个**故意不让它优化掉的调用点**，
用来量「实参 / 返回值落在哪个寄存器」：

| 函数 | 量什么 |
|---|---|
| `probe_call_by_value` | 4 字节 struct 按值传参 ⇒ 哪个寄存器、什么字节序 |
| `probe_ret_by_value` | 4 字节 struct 按值返回 ⇒ 哪个寄存器 |
| `probe_call_enum` | 1 字节 enum 实参 ⇒ 提升成几字节 |

## 跑

```bash
scripts/measure-abi.sh
```

（可选：设 `ARM_OBJDUMP` / `ARM_NM` 指向 `arm-none-eabi-*`；
默认从 `PATH` 找，MSYS2 的 `C:\msys64\ucrt64\bin` 里有一份。）

脚本会：
1. 用 **SDK 自己的 clang + 与 `vex/mkenv.mk` 一致的 flags** 编译成 `.o`
   （尤其 `-fshort-enums` —— 它会改 enum 宽度，选项变了结论就变）；
2. `nm -S` 打出布局测量表；
3. `objdump -d` 打出调用点的寄存器分配。

## 实测结果摘要

| 类型 | sizeof | alignof | packed? |
|---|---|---|---|
| `V5_DeviceT` | 4 | 4 | —（指针） |
| `V5_DeviceMotorPid` | 12 | **1** | ✅ |
| `V5_DeviceVisionRgb` | 4 | **1** | ✅ |
| `V5_TouchStatus` | 16 | 4 | ❌ |

- `V5_DeviceMotorPid.limit`（`uint16_t`）落在**偏移 6** ⇒ packed 的证据。
- ≤4 B 的 struct 按值传参 ⇒ **一个核心寄存器**（第 2 个实参 ⇒ `r1`），小端。
- ≤4 B 的 struct 按值返回 ⇒ **`r0`**。
- 1 字节 enum 传参 ⇒ `ldrb` 后**零扩展**到 32 位。

## 为什么要单独一个探针

C API 里**唯一**按值传的 struct 是 `V5_DeviceVisionRgb`（4 个函数传 / 4 个函数返回），
其余 struct 全走指针。但 JHYY 的 FFI **不支持 struct 按值跨边界**
（ABI v4.0.0 § 6），而且 `extern fn` 的参数类型**不做编译期检查** ——
声明 struct 参数**能编译通过**，但实际按地址传，**静默不符**。

⇒ 绑定面清单必须人工核对（见事实基线 § 9.2），
前提是**先知道 C 那头真实长什么样** —— 这就是本探针的活。

## 拆开看

```bash
arm-none-eabi-ar x libv5rt.a v5_apijump.c.obj                        # 纯 C API 的跳表桩
arm-none-eabi-objdump -d --section=.text.vexDeviceVisionWhiteBalanceSet v5_apijump.c.obj
```

SDK 桩里能看到它**从哪个寄存器取** struct（`str r1,[sp,#4]` … `ldr r1,[sp,#4]`）
⇒ 那是「固件那头要什么」的权威依据，跟调用方那头对上才算数。
