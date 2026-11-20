/* Benchmark runtime: a small Arduino-style layer the benchmark programs are
 * written against, so the same sources build for the RV328 and for an AVR.
 *   hal.c       RV328, real peripherals and interrupts (simulated chip)
 *   hal_null.c  any target: no peripherals, I/O returns at once. Leaves only the
 *               processor's own work, for the RV328-against-ATmega comparison.
 * F_CPU is 20 MHz for all divider settings; results are counted in clocks. */
#ifndef HAL_H
#define HAL_H
#include <stdint.h>
#ifndef F_CPU
#define F_CPU 20000000u
#endif
#if defined(__riscv) && !defined(HAL_NULL)
#define HAL_ISR __attribute__((section(".fast")))   /* interrupt path: linked first (see bench.ld.S) */
#else
#define HAL_ISR
#endif
void     hal_init(void);
void     hal_mark(unsigned n, uint32_t v);          /* measurement mark with a result value */
void     hal_done(void);
#define MARK(n, v) hal_mark((n), (v))
#define DONE()     hal_done()
uint32_t millis(void);
void     serial_begin(uint32_t baud);
void     serial_write(uint8_t c);
void     serial_print(const char *s);
unsigned serial_tx_free(void);
void     link_begin(void (*rx)(uint8_t data, unsigned overrun));  /* second serial port, receive interrupt */
void     hal_set_input(unsigned ch, unsigned mv);  /* test stimulus: voltage on an analog input */
uint16_t analog_read(unsigned ch);
void     pwm_write(unsigned duty);                 /* 10 bit */
void     spi_begin(void);
void     spi_write(uint8_t c);
void     pin_cs(unsigned which, unsigned level);   /* chip selects: 0 display, 1 card */
unsigned buttons_raw(void);                        /* three push buttons */
void     led_write(unsigned on);
void     probe_begin(void);                        /* external interrupt answered on a pin (latency probe) */
#endif
