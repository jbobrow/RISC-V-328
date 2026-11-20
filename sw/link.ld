/* RV328 linker script: code executes in place from the serial memory, data in SRAM. */
OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY {
	FLASH (rx)  : ORIGIN = 0x00000000, LENGTH = 32K
	RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 2K
}
SECTIONS {
	.text : {
		KEEP(*(.vectors))
		*(.text .text.*)
		*(.rodata .rodata.* .srodata .srodata.*)
		. = ALIGN(4);
	} > FLASH
	.data : {
		__data_start = .;
		__global_pointer$ = . + 0x800;
		*(.sdata .sdata.* .data .data.*)
		. = ALIGN(4);
		__data_end = .;
	} > RAM AT > FLASH
	__data_load = LOADADDR(.data);
	.bss (NOLOAD) : {
		__bss_start = .;
		*(.sbss .sbss.* .bss .bss.* COMMON)
		. = ALIGN(4);
		__bss_end = .;
	} > RAM
	__stack_top = ORIGIN(RAM) + LENGTH(RAM);
	/DISCARD/ : { *(.comment) *(.riscv.attributes) *(.note*) *(.eh_frame*) }
}
