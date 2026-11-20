/* CoreMark port for the RV328 simulation (see docs/cache_study.md).
 * Timing is taken by the testbench between two marks; nothing is printed by
 * the benchmark except through the testbench console. */
#ifndef CORE_PORTME_H
#define CORE_PORTME_H
#include <stddef.h>
#include <stdint.h>
#define HAS_FLOAT 0
#define HAS_TIME_H 0
#define USE_CLOCK 0
#define HAS_STDIO 0
#define HAS_PRINTF 0
#define COMPILER_VERSION "GCC" __VERSION__
#define COMPILER_FLAGS "-O2 -march=rv32imc"
#define MEM_LOCATION "STACK"
typedef int16_t  ee_s16;
typedef uint16_t ee_u16;
typedef int32_t  ee_s32;
typedef double   ee_f32;
typedef uint8_t  ee_u8;
typedef uint32_t ee_u32;
typedef ee_u32   ee_ptr_int;
typedef size_t   ee_size_t;
#define align_mem(x) (void *)(4 + (((ee_ptr_int)(x) - 1) & ~3))
#define CORETIMETYPE ee_u32
typedef ee_u32 CORE_TICKS;
#define SEED_METHOD SEED_VOLATILE
#define MEM_METHOD MEM_STACK
#define MULTITHREAD 1
#define USE_PTHREAD 0
#define USE_FORK 0
#define USE_SOCKET 0
#define MAIN_HAS_NOARGC 1
#define MAIN_HAS_NORETURN 0
#define PERFORMANCE_RUN 1
extern ee_u32 default_num_contexts;
typedef struct CORE_PORTABLE_S { ee_u8 portable_id; } core_portable;
void portable_init(core_portable *p, int *argc, char *argv[]);
void portable_fini(core_portable *p);
int  ee_printf(const char *fmt, ...);
#endif
