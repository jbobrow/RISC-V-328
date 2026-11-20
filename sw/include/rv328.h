/* RV328 register definitions. All peripheral registers are 32-bit and must be
 * accessed as words. Names follow the ATmega328PB where the function matches. */
#ifndef RV328_H
#define RV328_H
#include <stdint.h>

#define REG32(a)      (*(volatile uint32_t *)(a))
#define PERIPH(n)     (0x40000000u + ((n) << 8))

#define FLASH_BASE    0x00000000u
#define FLASH_SIZE    0x00008000u          /* 32 KB program area */
#define EEPROM_BASE   0x0001FC00u          /* 1 KB data area in the serial memory */
#define EEPROM_SIZE   0x00000400u
#define RAM_BASE      0x20000000u
#define RAM_SIZE      0x00000800u

/* ---- SYSCTL (slot 0) ---- */
#define CLKCR   REG32(PERIPH(0) + 0x00)
#define CLKPR   REG32(PERIPH(0) + 0x04)
#define OSCCAL  REG32(PERIPH(0) + 0x08)
#define SMCR    REG32(PERIPH(0) + 0x0C)
#define MCUSR   REG32(PERIPH(0) + 0x10)
#define PRR     REG32(PERIPH(0) + 0x14)
#define RSTCR   REG32(PERIPH(0) + 0x18)
#define BODCR   REG32(PERIPH(0) + 0x1C)
#define GPIOR0  REG32(PERIPH(0) + 0x20)
#define GPIOR1  REG32(PERIPH(0) + 0x24)
#define GPIOR2  REG32(PERIPH(0) + 0x28)
#define CHIPID  REG32(PERIPH(0) + 0x2C)
#define CLKSEL_RC 0
#define CLKSEL_X  1
#define CLKSEL_LF 2
#define XEN     (1u << 4)
#define XMODE(n) ((n) << 5)
#define RCDIS   (1u << 7)
#define CKOUT   (1u << 8)
#define XRDY    (1u << 16)
#define SLEEP_IDLE 0
#define SLEEP_ADC 1
#define SLEEP_PWR_DOWN 2
#define SLEEP_PWR_SAVE 3
#define SLEEP_STANDBY 6
#define SLEEP_EXT_STANDBY 7
#define PORF 1u
#define EXTRF 2u
#define BORF 4u
#define WDRF 8u
#define SWRF 16u
#define DBGRF 32u
#define SOFT_RESET() (RSTCR = 0xA5000100u)

/* ---- GPIO (slot 1) ---- */
#define PINB    REG32(PERIPH(1) + 0x00)
#define DDRB    REG32(PERIPH(1) + 0x04)
#define PORTB   REG32(PERIPH(1) + 0x08)
#define PCMSK0  REG32(PERIPH(1) + 0x0C)
#define PINC    REG32(PERIPH(1) + 0x10)
#define DDRC    REG32(PERIPH(1) + 0x14)
#define PORTC   REG32(PERIPH(1) + 0x18)
#define PCMSK1  REG32(PERIPH(1) + 0x1C)
#define PIND    REG32(PERIPH(1) + 0x20)
#define DDRD    REG32(PERIPH(1) + 0x24)
#define PORTD   REG32(PERIPH(1) + 0x28)
#define PCMSK2  REG32(PERIPH(1) + 0x2C)
#define PINE    REG32(PERIPH(1) + 0x30)
#define DDRE    REG32(PERIPH(1) + 0x34)
#define PORTE   REG32(PERIPH(1) + 0x38)
#define PCMSK3  REG32(PERIPH(1) + 0x3C)
#define PCICR   REG32(PERIPH(1) + 0x40)
#define PCIFR   REG32(PERIPH(1) + 0x44)
#define EICRA   REG32(PERIPH(1) + 0x48)
#define EIMSK   REG32(PERIPH(1) + 0x4C)
#define EIFR    REG32(PERIPH(1) + 0x50)

/* ---- timers: TC0, TC2 are 8-bit; TC1, TC3, TC4 are 16-bit ---- */
typedef struct {
	volatile uint32_t CR, CNT, OCRA, OCRB, ICR, IER, IFR, FOC;
} tc_t;
#define TC0 ((tc_t *)PERIPH(2))
#define TC1 ((tc_t *)PERIPH(3))
#define TC2 ((tc_t *)PERIPH(4))
#define TC3 ((tc_t *)PERIPH(5))
#define TC4 ((tc_t *)PERIPH(6))
#define TC_CS(n)    (n)          /* 0 stop 1 /1 2 /8 3 /32 4 /64 5 /128 6 /256 7 /1024 8 Tn fall 9 Tn rise 10 async */
#define TC_WGM_NORMAL (0u << 4)
#define TC_WGM_FAST   (1u << 4)
#define TC_WGM_PC     (2u << 4)
#define TC_WGM_PFC    (3u << 4)
#define TC_TOP_MAX    (0u << 6)
#define TC_TOP_OCRA   (1u << 6)
#define TC_TOP_ICR    (2u << 6)
#define TC_TOP_8BIT   (3u << 6)
#define TC_TOP_9BIT   (4u << 6)
#define TC_TOP_10BIT  (5u << 6)
#define TC_COMA(n)    ((n) << 9)
#define TC_COMB(n)    ((n) << 11)
#define TC_ICNC       (1u << 13)
#define TC_ICES       (1u << 14)
#define TC_OVF 1u
#define TC_OCA 2u
#define TC_OCB 4u
#define TC_IC  8u

/* ---- USART ---- */
typedef struct { volatile uint32_t DATA, SR, CR, FMT, BRR; } usart_t;
#define USART0 ((usart_t *)PERIPH(7))
#define USART1 ((usart_t *)PERIPH(8))
#define RXC 0x80u
#define TXC 0x40u
#define UDRE 0x20u
#define FE 0x10u
#define DOR 0x08u
#define UPE 0x04u
#define RXCIE 0x80u
#define TXCIE 0x40u
#define UDRIE 0x20u
#define RXEN 0x10u
#define TXEN 0x08u
#define U2X 0x02u
#define USART_8N1 3u
#define USART_BITS(n) ((n) - 5)
#define USART_2STOP 0x08u
#define USART_EVEN 0x20u
#define USART_ODD 0x30u

/* ---- SPI ---- */
typedef struct { volatile uint32_t CR, SR, DATA; } spi_t;
#define SPI0 ((spi_t *)PERIPH(9))
#define SPI1 ((spi_t *)PERIPH(10))
#define SPI2X 0x100u
#define SPIE 0x80u
#define SPE 0x40u
#define DORD 0x20u
#define MSTR 0x10u
#define CPOL 0x08u
#define CPHA 0x04u
#define SPIF 0x80u
#define WCOL 0x40u

/* ---- TWI ---- */
typedef struct { volatile uint32_t BR, SR, AR, DR, CR, AMR; } twi_t;
#define TWI0 ((twi_t *)PERIPH(11))
#define TWI1 ((twi_t *)PERIPH(12))
#define TWINT 0x80u
#define TWEA 0x40u
#define TWSTA 0x20u
#define TWSTO 0x10u
#define TWWC 0x08u
#define TWEN 0x04u
#define TWIE 0x01u

/* ---- ADC and analog comparator (slot 13) ---- */
#define ADMUX   REG32(PERIPH(13) + 0x00)
#define ADCSRA  REG32(PERIPH(13) + 0x04)
#define ADC     REG32(PERIPH(13) + 0x08)
#define ADCSRB  REG32(PERIPH(13) + 0x0C)
#define DIDR0   REG32(PERIPH(13) + 0x10)
#define ACSR    REG32(PERIPH(13) + 0x20)
#define DIDR1   REG32(PERIPH(13) + 0x24)
#define REFS_AREF (0u << 6)
#define REFS_AVCC (1u << 6)
#define REFS_1V1  (3u << 6)
#define ADLAR 0x20u
#define ADEN 0x80u
#define ADSC 0x40u
#define ADATE 0x20u
#define ADIF 0x10u
#define ADIE 0x08u
#define ACME 0x40u
#define ACOE 0x100u
#define ACD 0x80u
#define ACBG 0x40u
#define ACO 0x20u
#define ACI 0x10u
#define ACIE 0x08u
#define ACIC 0x04u

/* ---- watchdog (slot 14) ---- */
#define WDTCSR  REG32(PERIPH(14) + 0x00)
#define WDR     REG32(PERIPH(14) + 0x04)
#define WDT_KEY 0xA5000000u
#define WDIF 0x80u
#define WDIE 0x40u
#define WDE  0x10u
#define wdt_reset() (WDR = 0x5A)

/* ---- NVM controller (slot 15) ---- */
#define NVMCR   REG32(PERIPH(15) + 0x00)
#define NVMSR   REG32(PERIPH(15) + 0x04)
#define NVMADDR REG32(PERIPH(15) + 0x08)
#define NVMDATA REG32(PERIPH(15) + 0x0C)
#define NVMCFG  REG32(PERIPH(15) + 0x10)
#define NVM_KEY 0xA5000000u
#define NVM_WRITE(nbytes) (NVM_KEY | 1u | (((nbytes) - 1u) << 4))
#define NVM_ERASE (NVM_KEY | 2u)
#define NVM_FLUSH (NVM_KEY | 3u)
#define NVM_BUSY 1u
#define NVM_DONE 2u
#define NVM_DONEIE 4u

/* ---- interrupts ---- */
enum {
	IRQ_INT0, IRQ_INT1, IRQ_PCINT0, IRQ_PCINT1, IRQ_PCINT2, IRQ_PCINT3, IRQ_WDT,
	IRQ_TC0, IRQ_TC1, IRQ_TC2, IRQ_TC3, IRQ_TC4, IRQ_SPI0, IRQ_SPI1, IRQ_USART0,
	IRQ_USART1, IRQ_TWI0, IRQ_TWI1, IRQ_ADC, IRQ_AC, IRQ_NVM, IRQ_COUNT
};
typedef void (*irq_handler_t)(void);
void irq_attach(unsigned irq, irq_handler_t fn);   /* install handler and enable the line */
void irq_detach(unsigned irq);

static inline void sei(void) { __asm__ volatile("csrsi mstatus, 8"); }
static inline void cli(void) { __asm__ volatile("csrci mstatus, 8"); }
static inline void sleep_cpu(void) { __asm__ volatile("wfi"); }
static inline void set_sleep_mode(unsigned m) { SMCR = m; }

/* EEPROM-style access to the data area of the serial memory */
uint8_t eeprom_read_byte(uint32_t addr);
void    eeprom_write_byte(uint32_t addr, uint8_t v);
void    nvm_write_word(uint32_t offset, uint32_t v);   /* offset is word-aligned, from FLASH_BASE */
#endif
