/* RV328 startup code and interrupt dispatch. */
#define MEIEA   0xbe0
#define MEINEXT 0xbe4
#define MSLEEP  0xbf0

	.section .vectors, "ax"
	.global _start
_start:
	/* Clear the registers. On silicon they power up holding some value and the code below
	   never reads one before writing it, but gate-level simulation starts them unknown, and the
	   synthesized decoder lets an unknown in a field an instruction ignores (rs1 of lui) reach
	   its result. sp and gp are loaded next. */
	.irp r, 1,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31
	li   x\r, 0
	.endr
	.option push
	.option norelax
	la   gp, __global_pointer$
	.option pop
	la   sp, __stack_top
	la   t0, _trap
	csrw mtvec, t0
	/* WFI gates the CPU clock and hands the sleep mode in SMCR to the clock controller */
	li   t0, 3
	csrw MSLEEP, t0
	/* copy .data, clear .bss */
	la   a0, __data_load
	la   a1, __data_start
	la   a2, __data_end
1:	bgeu a1, a2, 2f
	lw   t0, 0(a0)
	sw   t0, 0(a1)
	addi a0, a0, 4
	addi a1, a1, 4
	j    1b
2:	la   a1, __bss_start
	la   a2, __bss_end
3:	bgeu a1, a2, 4f
	sw   zero, 0(a1)
	addi a1, a1, 4
	j    3b
4:	li   t0, 0x800          /* mie.MEIE: external interrupts */
	csrs mie, t0
	call main
5:	wfi
	j    5b

	.section .text._trap, "ax"
	.balign 4
_trap:
	addi sp, sp, -64
	sw   ra, 0(sp)
	sw   t0, 4(sp)
	sw   t1, 8(sp)
	sw   t2, 12(sp)
	sw   a0, 16(sp)
	sw   a1, 20(sp)
	sw   a2, 24(sp)
	sw   a3, 28(sp)
	sw   a4, 32(sp)
	sw   a5, 36(sp)
	sw   a6, 40(sp)
	sw   a7, 44(sp)
	sw   t3, 48(sp)
	sw   t4, 52(sp)
	sw   t5, 56(sp)
	sw   t6, 60(sp)
	csrr t0, mcause
	bgez t0, 9f             /* exception: hand over to fault handler */
1:	csrr a0, MEINEXT        /* bit 31 set: nothing pending; else IRQ number << 2 */
	bltz a0, 2f
	la   t0, __irq_table
	add  t0, t0, a0
	lw   t0, 0(t0)
	jalr t0
	j    1b
2:	lw   ra, 0(sp)
	lw   t0, 4(sp)
	lw   t1, 8(sp)
	lw   t2, 12(sp)
	lw   a0, 16(sp)
	lw   a1, 20(sp)
	lw   a2, 24(sp)
	lw   a3, 28(sp)
	lw   a4, 32(sp)
	lw   a5, 36(sp)
	lw   a6, 40(sp)
	lw   a7, 44(sp)
	lw   t3, 48(sp)
	lw   t4, 52(sp)
	lw   t5, 56(sp)
	lw   t6, 60(sp)
	addi sp, sp, 64
	mret
9:	csrr a0, mcause
	csrr a1, mepc
	call fault_handler
	j    9b
