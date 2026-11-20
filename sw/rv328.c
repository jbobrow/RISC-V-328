/* RV328 runtime support: interrupt table, NVM/EEPROM helpers. */
#include "rv328.h"

static void irq_default(void) { for (;;) ; }
irq_handler_t __irq_table[IRQ_COUNT] = {
	[0 ... IRQ_COUNT - 1] = irq_default
};

__attribute__((weak)) void fault_handler(uint32_t cause, uint32_t epc)
{
	GPIOR1 = cause; GPIOR2 = epc; GPIOR0 = 0xDEAD0000u | (cause & 0xffff);
	for (;;) ;
}

/* meiea is a windowed array: bits 31:16 hold 16 enable bits, bits 4:0 the window index */
static void irq_enable(unsigned irq, int on)
{
	uint32_t v = (0x10000u << (irq & 15)) | (irq >> 4);
	if (on) __asm__ volatile("csrs 0xbe0, %0" : : "r"(v));
	else    __asm__ volatile("csrc 0xbe0, %0" : : "r"(v));
}
void irq_attach(unsigned irq, irq_handler_t fn) { __irq_table[irq] = fn; irq_enable(irq, 1); }
void irq_detach(unsigned irq) { irq_enable(irq, 0); __irq_table[irq] = irq_default; }

void nvm_write_word(uint32_t offset, uint32_t v)
{
	NVMADDR = offset; NVMDATA = v; NVMCR = NVM_WRITE(4);
	while (NVMSR & NVM_BUSY) ;
}
uint8_t eeprom_read_byte(uint32_t addr) { return *(volatile uint8_t *)(EEPROM_BASE + addr); }
void eeprom_write_byte(uint32_t addr, uint8_t v)
{
	NVMADDR = EEPROM_BASE + addr; NVMDATA = v; NVMCR = NVM_WRITE(1);
	while (NVMSR & NVM_BUSY) ;
}
