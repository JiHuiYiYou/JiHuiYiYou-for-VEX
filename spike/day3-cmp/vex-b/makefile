# VEXcode makefile 2019_03_26_01
#
# ★ 与 day0-c / day1-emit 的 makefile 只差两处：
#   ① OBJ 里**加上 src/*.s**（B 路：JHYY → ARM 汇编，不是 C）
#   ② 补一条 .s 的汇编规则（SDK 的 mkrules.mk 只有 .c / .cpp）
#
# 汇编用 SDK 的 clang（`-target thumbv7-none-eabi -march=armv7-a`），
# 而生成的 .s 里写了 `.arm` ⇒ **ARM 态 4 字节定长**（事实基线 § 4）。

VERBOSE = 0

# include toolchain options
include vex/mkenv.mk

# location of the project source files
SRC_C  = $(wildcard src/*.cpp)
SRC_C += $(wildcard src/*.c)
SRC_S  = $(wildcard src/*.s)

OBJ = $(addprefix $(BUILD)/, $(addsuffix .o, $(basename $(SRC_C))) )
OBJ += $(addprefix $(BUILD)/, $(addsuffix .o, $(basename $(SRC_S))) )

# location of headers that .c/.s files depend on
SRC_H  = $(wildcard include/*.h)

# other dependancies
SRC_A  = makefile

# project header file locations
INC_F  = include

# build targets
all: $(BUILD)/$(PROJECT).bin

# include build rules
include vex/mkrules.mk

# ★ B 路：汇编规则（SDK 的 mkrules.mk 里没有）
$(BUILD)/%.o: %.s $(SRC_H) $(SRC_A)
	$(Q)$(CC) $(CFLAGS) -c -o $@ $<
