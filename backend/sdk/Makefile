# SDK Makefile for LPC2148 + FreeRTOS

TOOLCHAIN_BIN = C:/Users/puroh/.gemini/antigravity-ide/scratch/arm-gcc/xpack-arm-none-eabi-gcc-13.2.1-1.1/bin
CC = $(TOOLCHAIN_BIN)/arm-none-eabi-gcc
OBJCOPY = $(TOOLCHAIN_BIN)/arm-none-eabi-objcopy

# Target source file (can be overridden on command line)
TARGET_C ?= main.c
TARGET_ELF = firmware.elf
TARGET_MAP = firmware.map
TARGET_HEX = firmware.hex

# Include directories
INCLUDES = -I. \
           -IFreeRTOS/include \
           -IFreeRTOS/portable/GCC/ARM7_LPC2000 \
           -ILPC2148

# Compiler flags for ARM7TDMI
CFLAGS = -mcpu=arm7tdmi \
         -marm \
         -std=gnu99 \
         -Wall \
         -Wextra \
         -Os \
         $(INCLUDES)

# Linker flags
LDFLAGS = -T LPC2148/lpc2148.ld \
          -nostartfiles \
          -Wl,-Map=$(TARGET_MAP) \
          -Wl,--gc-sections

# Source files
SDK_SRCS = LPC2148/startup.S \
           FreeRTOS/source/tasks.c \
           FreeRTOS/source/queue.c \
           FreeRTOS/source/list.c \
           FreeRTOS/source/heap_4.c \
           FreeRTOS/portable/GCC/ARM7_LPC2000/port.c \
           FreeRTOS/portable/GCC/ARM7_LPC2000/portISR.c

ALL_SRCS = $(TARGET_C) $(SDK_SRCS)
OBJS = $(patsubst %.c,%.o,$(patsubst %.S,%.o,$(ALL_SRCS)))

# Default target
all: $(TARGET_ELF) $(TARGET_HEX)

$(TARGET_ELF): $(ALL_SRCS)
	$(CC) $(CFLAGS) $(ALL_SRCS) $(LDFLAGS) -o $(TARGET_ELF)

$(TARGET_HEX): $(TARGET_ELF)
	$(OBJCOPY) -O ihex $(TARGET_ELF) $(TARGET_HEX)

ifeq ($(OS),Windows_NT)
    CLEAN_CMD = -del /f /q $(TARGET_ELF) $(TARGET_HEX) $(TARGET_MAP) *.o 2>nul
else
    CLEAN_CMD = -rm -f $(TARGET_ELF) $(TARGET_HEX) $(TARGET_MAP) *.o
endif

clean:
	$(CLEAN_CMD)

.PHONY: all clean
