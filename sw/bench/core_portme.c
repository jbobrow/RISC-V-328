/* CoreMark port for the RV328 simulation. */
#include <stdarg.h>
#include <stdio.h>
#include "coremark.h"
#include "rv328.h"
#include "hal.h"

volatile ee_s32 seed1_volatile = 0x0;
volatile ee_s32 seed2_volatile = 0x0;
volatile ee_s32 seed3_volatile = 0x66;
volatile ee_s32 seed4_volatile = ITERATIONS;
volatile ee_s32 seed5_volatile = 0;
ee_u32 default_num_contexts = 1;

/* time base for the benchmark's own bookkeeping: timer 3 at clock/64 */
static CORETIMETYPE t_start, t_stop;
void start_time(void) { TC3->CNT = 0; MARK(1, 0); t_start = 0; }
void stop_time(void)  { MARK(2, 0); t_stop = TC3->CNT; }
CORE_TICKS get_time(void) { return t_stop - t_start; }
secs_ret time_in_secs(CORE_TICKS ticks) { return ticks / (F_CPU / 64u); }

/* console through the testbench: GPIOR2 = character, GPIOR1 alternates 0x60xx */
int ee_printf(const char *fmt, ...)
{
	static char buf[96];
	static unsigned flip;
	va_list ap;
	va_start(ap, fmt);
	int n = vsnprintf(buf, sizeof buf, fmt, ap);
	va_end(ap);
	for (const char *p = buf; *p; p++) { GPIOR2 = (uint8_t)*p; GPIOR1 = 0x6000u | (flip++ & 1u); }
	return n;
}
void portable_init(core_portable *p, int *argc, char *argv[])
{
	(void)argc; (void)argv;
	hal_init();
	TC3->CR = TC_CS(4);
	p->portable_id = 1;
}
void portable_fini(core_portable *p)
{
	p->portable_id = 0;
	DONE();
}
