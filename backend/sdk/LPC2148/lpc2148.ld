/* Linker script for LPC2148 */

ENTRY(_start)

MEMORY
{
    flash (rx)  : ORIGIN = 0x00000000, LENGTH = 512K
    ram   (rwx) : ORIGIN = 0x40000000, LENGTH = 32K
}

SECTIONS
{
    /* Startup vector table placed at the very beginning of Flash */
    .vectors :
    {
        KEEP(*(.vectors))
    } > flash

    /* Text section (code) and read-only data */
    .text :
    {
        *(.text)
        *(.text.*)
        *(.rodata)
        *(.rodata.*)
        *(.glue_7)
        *(.glue_7t)
        _etext = .;
    } > flash

    /* Location of initialized data in flash */
    _sidata = LOADADDR(.data);

    /* Initialized data in RAM */
    .data :
    {
        _sdata = .;
        *(.data)
        *(.data.*)
        . = ALIGN(4);
        _edata = .;
    } > ram AT > flash

    /* Uninitialized data in RAM */
    .bss :
    {
        _sbss = .;
        __bss_start__ = _sbss;
        *(.bss)
        *(.bss.*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
        __bss_end__ = _ebss;
    } > ram

    /* Heap allocation */
    .heap :
    {
        . = ALIGN(4);
        _sheap = .;
        . = . + 4K; /* Allocate 4KB for heap */
        _eheap = .;
    } > ram

    /* Stack allocations for ARM modes */
    .stack :
    {
        . = ALIGN(8);
        
        /* Undefined Instruction stack */
        _stack_und_start = .;
        . = . + 256;
        _stack_und_end = .;
        
        /* Abort stack */
        _stack_abt_start = .;
        . = . + 256;
        _stack_abt_end = .;
        
        /* FIQ stack */
        _stack_fiq_start = .;
        . = . + 256;
        _stack_fiq_end = .;
        
        /* IRQ stack */
        _stack_irq_start = .;
        . = . + 1K;
        _stack_irq_end = .;
        
        /* Supervisor stack (used by RTOS scheduler) */
        _stack_svc_start = .;
        . = . + 2K;
        _stack_svc_end = .;
        
        /* System/User stack (used by tasks before scheduler starts) */
        _stack_usr_start = .;
        . = . + 2K;
        _stack_usr_end = .;
        
        _stack_end = .;
    } > ram

    _estack = _stack_usr_end;
}
