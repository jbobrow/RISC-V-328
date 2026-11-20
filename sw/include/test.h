/* Helpers shared by the simulation tests. */
#ifndef TEST_H
#define TEST_H
#include "rv328.h"
#define CHECK(n, c) do { if (!(c)) { GPIOR0 = 0xBAD00000u | (n); for (;;) ; } } while (0)
#define PASS()      do { GPIOR0 = 0x600D600Du; for (;;) ; } while (0)
#define TBHOOK(v)   (GPIOR1 = (v))            /* testbench action, see tb/tb.v */
#define TBVAL(v)    (GPIOR2 = (v))
static inline void delay(volatile unsigned n) { while (n--) ; }
#endif
