/* RV328 linker script for the benchmark programs (C library with thread-local errno).
 * Preprocessed with RAM_KB = 2 (the chip) or 4 (simulation-only RAM for CoreMark). */
OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY {
	FLASH (rx)  : ORIGIN = 0x00000000, LENGTH = 32K
	RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = RAM_KB * 1024
}
SECTIONS {
	.text : {
		KEEP(*(.vectors))
		*(.text._trap)
		*(.fast .fast.*)                 /* interrupt handlers (HAL_ISR): start of the image */
		__fast_end = .;
		*(.text .text.*)
		*(.rodata .rodata.* .srodata .srodata.*)
		. = ALIGN(4);
	} > FLASH
	.data : {
		__data_start = .;
		__global_pointer$ = . + 0x800;
		*(.sdata .sdata.* .data .data.*)
		. = ALIGN(4);
	} > RAM AT > FLASH
	__data_load = LOADADDR(.data);
	.tdata : {
		__tls_base = .;
		*(.tdata .tdata.*)
		. = ALIGN(4);
	} > RAM AT > FLASH
	__data_end = ADDR(.tdata) + SIZEOF(.tdata);
	.tbss (NOLOAD) : { *(.tbss .tbss.* .tcommon) } > RAM
	.tbss_space (NOLOAD) : { . = . + SIZEOF(.tbss); . = ALIGN(4); } > RAM
	.bss (NOLOAD) : {
		__bss_start = .;
		*(.sbss .sbss.* .bss .bss.* COMMON)
		. = ALIGN(4);
		__bss_end = .;
	} > RAM
	__stack_top = ORIGIN(RAM) + LENGTH(RAM);
	/DISCARD/ : { *(.comment) *(.riscv.attributes) *(.note*) *(.eh_frame*) }
}
