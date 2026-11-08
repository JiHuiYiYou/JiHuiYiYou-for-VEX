# Day 0 探针（手写 C，零 JHYY 变量）

> 这一步的目的**不是**"用 C 写 VEX"，而是**把 VEX 侧的未知数全部变成实测值**。
> 事实见 [`../../docs/00-事实基线.md`](../../docs/00-事实基线.md)。

## 它做什么

`src/main.c` 只做四件事：

1. `vexDeviceGetByIndex(0)` 取设备句柄 ⇒ 确认 C API 的 device 模型是**句柄**不是端口号
2. 配齿比 / 制动模式 / 编码器单位 ⇒ 确认 `vex::motor` 构造函数那些配置的 C 层等价物
3. `vexDeviceMotorVelocitySet(50)` → `vexDelay(500)` → 归零 ⇒ 转 0.5 秒
4. `vexDisplayPrintf(1, 1, 0, "day0-c alive")` ⇒ Brain 屏显

主循环带 `vexDelay(100)` —— 因为**用户的 `main` 是一个 task**（`vexTaskAdd(main, 2, "MAIN")`），
不让出时间片会顶掉别的 task。

## 自己编一遍

```bash
scripts/build-vex.sh spike/day0-c day0c
```

或直接：

```bash
cd spike/day0-c
make T="C:/Program Files (x86)/VEX Robotics/VEXcode Pro V5/sdk" P=day0c
```

产物：`build/day0c.{elf,bin,map}`。**已验证**：`day0c.bin` 2756 B，头 32 字节
`XVX5` + 版本 1，入口 `0x03800020`；用户 `main` 只占 120 B。

## 烧进 Brain（⏳ 待测 —— 需要硬件）

1. 把 `program.bin`（= `build/day0c.bin`）放到 microSD 卡**根目录**
2. 卡插进 V5 Brain 的 SD 卡槽
3. Brain 屏上选这个程序运行
4. 预期：**PORT1 的电机转 0.5 秒**，Brain 屏显示 `day0-c alive`

> 备选路径：VEXcode Pro 的「Download」按钮直连烧录 —— **待测**
> （那条路可能要求 `.v5code` 工程而不是裸 `.bin`）。

## 待测清单（勾掉就更新事实基线）

- [ ] 电机真的转了 0.5 秒（PORT1）
- [ ] Brain 屏显示 `day0-c alive`
- [ ] `vexDisplayPrintf` 的 (x, y) 坐标语义（原点在哪？单位？）
- [ ] `vexTasksRun` 的 tick 频率（消息泵频率 —— 规格书八项里唯一还缺的一条）
- [ ] `.heap` 那 1 MB 在实机上是否真可用（`malloc` 试一下）
- [ ] SD 卡直插 vs VEXcode Pro 下载按钮，哪条是竞赛里更顺手的

## 拆开看

```bash
arm-none-eabi-objdump -d --start-address=0x03800020 build/day0c.elf   # 入口 vexStartup
arm-none-eabi-objdump -r build/day0c.elf | head -40                   # 重定位 = 权威调用关系
arm-none-eabi-readelf -h build/day0c.elf                              # Machine / Flags / Entry
```
