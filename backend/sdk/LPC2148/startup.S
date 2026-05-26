/* LPC2148 Assembly Startup File */

.section .vectors, "ax"
.arm

/* Interrupt Vector Table */
.global _start
_start:
    ldr pc, =reset_handler          /* Reset Vector */
    ldr pc, =und_handler            /* Undefined Instruction */
    ldr pc, =vPortYieldProcessor    /* Software Interrupt (SWI) */
    ldr pc, =pabt_handler           /* Prefetch Abort */
    ldr pc, =dabt_handler           /* Data Abort */
    .word 0xB9205F80                /* Reserved / Boot Checksum (optional, 0xB9205F80 for valid LPC2000 boot) */
    ldr pc, [pc, #-0x0120]          /* IRQ Vector (loads address from VICVectAddr) */
    ldr pc, =fiq_handler            /* FIQ Vector */

.section .text
.arm

/* Standard Mode Constants */
.equ MODE_USR, 0x10
.equ MODE_FIQ, 0x11
.equ MODE_IRQ, 0x12
.equ MODE_SVC, 0x13
.equ MODE_ABT, 0x17
.equ MODE_UND, 0x1B
.equ MODE_SYS, 0x1F

.equ I_BIT, 0x80
.equ F_BIT, 0x40

/* Reset Handler */
.global reset_handler
reset_handler:
    /* Set up stack pointers for each mode */
    
    /* Undefined Instruction Mode */
    msr cpsr_c, #MODE_UND | I_BIT | F_BIT
    ldr sp, =_stack_und_end
    
    /* Abort Mode */
    msr cpsr_c, #MODE_ABT | I_BIT | F_BIT
    ldr sp, =_stack_abt_end
    
    /* FIQ Mode */
    msr cpsr_c, #MODE_FIQ | I_BIT | F_BIT
    ldr sp, =_stack_fiq_end
    
    /* IRQ Mode */
    msr cpsr_c, #MODE_IRQ | I_BIT | F_BIT
    ldr sp, =_stack_irq_end
    
    /* Supervisor Mode (SVC) */
    msr cpsr_c, #MODE_SVC | I_BIT | F_BIT
    ldr sp, =_stack_svc_end
    
    /* System/User Mode */
    msr cpsr_c, #MODE_SYS | I_BIT | F_BIT
    ldr sp, =_stack_usr_end

    /* Copy initialized data from Flash to RAM */
    ldr r0, =_sidata
    ldr r1, =_sdata
    ldr r2, =_edata
copy_data_loop:
    cmp r1, r2
    ldrcc r3, [r0], #4
    strcc r3, [r1], #4
    bcc copy_data_loop

    /* Clear uninitialized data (BSS) section in RAM */
    ldr r1, =_sbss
    ldr r2, =_ebss
    mov r3, #0
clear_bss_loop:
    cmp r1, r2
    strcc r3, [r1], #4
    bcc clear_bss_loop

    /* Branch to main */
    ldr r0, =main
    bx r0

/* Dummy Exception Handlers */
und_handler:
    b und_handler

pabt_handler:
    b pabt_handler

dabt_handler:
    b dabt_handler

fiq_handler:
    b fiq_handler
