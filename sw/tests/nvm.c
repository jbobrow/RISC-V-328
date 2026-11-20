/* Program memory and EEPROM area: read through the cache, byte and word
 * writes, done interrupt, cache invalidation, SCK divider. */
#include "test.h"
static volatile uint32_t done_n;
static void nvm_isr(void) { done_n++; NVMSR = NVM_DONE | NVM_DONEIE; }
static const uint32_t table[4] = { 0xCAFEBABE, 0x8BADF00D, 0x01234567, 0x89ABCDEF };
int main(void)
{
	volatile const uint32_t *t = table;
	CHECK(1, t[0] == 0xCAFEBABE && t[3] == 0x89ABCDEF);
	/* EEPROM area starts erased */
	CHECK(2, eeprom_read_byte(0) == 0xFF && eeprom_read_byte(1023) == 0xFF);
	eeprom_write_byte(0, 0x12);
	eeprom_write_byte(5, 0x34);
	eeprom_write_byte(1023, 0x56);
	CHECK(3, eeprom_read_byte(0) == 0x12 && eeprom_read_byte(5) == 0x34 && eeprom_read_byte(1023) == 0x56);
	CHECK(4, eeprom_read_byte(1) == 0xFF && eeprom_read_byte(4) == 0xFF);
	eeprom_write_byte(5, 0x35);                       /* rewrite without erase */
	CHECK(5, eeprom_read_byte(5) == 0x35);

	/* self-programming: word write into unused program space, with interrupt */
	irq_attach(IRQ_NVM, nvm_isr);
	sei();
	NVMSR = NVM_DONE | NVM_DONEIE;
	NVMADDR = 0x7000; NVMDATA = 0xA1B2C3D4; NVMCR = NVM_WRITE(4);
	CHECK(6, NVMSR & NVM_BUSY);
	while (!done_n) ;
	CHECK(7, REG32(0x7000) == 0xA1B2C3D4 && !(NVMSR & NVM_BUSY));
	/* a write without the key is ignored */
	NVMADDR = 0x7004; NVMDATA = 0x11111111; NVMCR = 0x31;
	delay(20);
	CHECK(8, !(NVMSR & NVM_BUSY) && REG32(0x7004) == 0xFFFFFFFF);
	/* faster and slower serial clock still read correctly after a flush */
	NVMCFG = 0; NVMCR = NVM_FLUSH;
	CHECK(9, t[1] == 0x8BADF00D && REG32(0x7000) == 0xA1B2C3D4);
	NVMCFG = 3; NVMCR = NVM_FLUSH;
	CHECK(10, t[2] == 0x01234567 && eeprom_read_byte(1023) == 0x56);
	PASS();
}
