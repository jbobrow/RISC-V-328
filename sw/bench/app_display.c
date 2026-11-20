/* Benchmark "display": an integer-only user interface. A 128x32 one-bit frame
 * buffer, text from a glyph table in program memory, five different screens
 * shown in turn, and the frame pushed to the display over SPI each pass. */
#include <string.h>
#include "hal.h"
#include "font5x7.h"
#define W 128
#define H 32
#define ROUNDS 4
static uint8_t fb[W * H / 8];
static uint8_t hist[64];
static unsigned hist_n;
static uint8_t btn_state, btn_cnt[3], sel;

static void fb_pixel(int x, int y, int on)
{
	if ((unsigned)x >= W || (unsigned)y >= H) return;
	uint8_t m = (uint8_t)(1u << (y & 7));
	if (on) fb[x + (y >> 3) * W] |= m; else fb[x + (y >> 3) * W] &= (uint8_t)~m;
}
static void fb_hline(int x, int y, int w, int on) { while (w-- > 0) fb_pixel(x++, y, on); }
static void fb_vline(int x, int y, int h, int on) { while (h-- > 0) fb_pixel(x, y++, on); }
static void fb_rect(int x, int y, int w, int h)
{
	fb_hline(x, y, w, 1); fb_hline(x, y + h - 1, w, 1);
	fb_vline(x, y, h, 1); fb_vline(x + w - 1, y, h, 1);
}
static void fb_fill(int x, int y, int w, int h, int on) { while (h-- > 0) fb_hline(x, y++, w, on); }
static void fb_line(int x0, int y0, int x1, int y1)
{
	int dx = x1 > x0 ? x1 - x0 : x0 - x1, sx = x0 < x1 ? 1 : -1;
	int dy = y1 > y0 ? y0 - y1 : y1 - y0, sy = y0 < y1 ? 1 : -1;
	int e = dx + dy;
	for (;;) {
		fb_pixel(x0, y0, 1);
		if (x0 == x1 && y0 == y1) break;
		int e2 = 2 * e;
		if (e2 >= dy) { e += dy; x0 += sx; }
		if (e2 <= dx) { e += dx; y0 += sy; }
	}
}
static void fb_circle(int cx, int cy, int r)
{
	int x = r, y = 0, e = 1 - r;
	while (x >= y) {
		fb_pixel(cx + x, cy + y, 1); fb_pixel(cx - x, cy + y, 1);
		fb_pixel(cx + x, cy - y, 1); fb_pixel(cx - x, cy - y, 1);
		fb_pixel(cx + y, cy + x, 1); fb_pixel(cx - y, cy + x, 1);
		fb_pixel(cx + y, cy - x, 1); fb_pixel(cx - y, cy - x, 1);
		y++;
		if (e < 0) e += 2 * y + 1; else { x--; e += 2 * (y - x) + 1; }
	}
}
static int fb_char(int x, int y, char c, int inv)
{
	const uint8_t *g = font5x7[(uint8_t)(c - 0x20) % 96u];
	for (int i = 0; i < 5; i++) {
		uint8_t col = g[i];
		for (int j = 0; j < 7; j++) fb_pixel(x + i, y + j, ((col >> j) & 1) ^ inv);
	}
	for (int j = 0; j < 7; j++) fb_pixel(x + 5, y + j, inv);
	return x + 6;
}
static int fb_text(int x, int y, const char *s, int inv) { while (*s) x = fb_char(x, y, *s++, inv); return x; }
static int fb_num(int x, int y, int32_t v, unsigned digits, int inv)
{
	char b[12]; unsigned n = 0; uint32_t u = v < 0 ? (uint32_t)-v : (uint32_t)v;
	do { b[n++] = (char)('0' + u % 10u); u /= 10u; } while (u || n < digits);
	if (v < 0) x = fb_char(x, y, '-', inv);
	while (n) x = fb_char(x, y, b[--n], inv);
	return x;
}
static void fb_flush(void)
{
	pin_cs(0, 0);
	for (unsigned i = 0; i < sizeof fb; i++) spi_write(fb[i]);
	pin_cs(0, 1);
}
static void buttons(void)
{
	uint8_t raw = (uint8_t)buttons_raw();
	for (unsigned i = 0; i < 3; i++) {
		uint8_t b = (raw >> i) & 1u;
		if (b == ((btn_state >> i) & 1u)) btn_cnt[i] = 0;
		else if (++btn_cnt[i] >= 3) { btn_state ^= (uint8_t)(1u << i); btn_cnt[i] = 0; if (b) sel = (uint8_t)((sel + 1u) % 6u); }
	}
}

static void screen_home(uint32_t ms)
{
	uint32_t s = ms / 1000u;
	int x = fb_num(2, 2, (int32_t)(s / 3600u % 24u), 2, 0);
	x = fb_char(x, 2, ':', 0); x = fb_num(x, 2, (int32_t)(s / 60u % 60u), 2, 0);
	x = fb_char(x, 2, ':', 0); fb_num(x, 2, (int32_t)(s % 60u), 2, 0);
	fb_text(2, 12, "TEMP", 0); fb_num(40, 12, hist[(hist_n - 1u) % 64u], 3, 0);
	fb_text(2, 22, "BATT", 0); fb_num(40, 22, 3700 + (int32_t)(ms % 97u), 4, 0);
	fb_rect(90, 2, 36, 28);
	fb_fill(92, 4, (int)(ms / 8u % 32u), 24, 1);
}
static void screen_graph(void)
{
	fb_rect(0, 0, W, H);
	for (unsigned i = 1; i < 64; i++) {
		int a = hist[(hist_n + i - 1u) % 64u], b = hist[(hist_n + i) % 64u];
		fb_line((int)(2 * i - 2), H - 2 - a * (H - 4) / 255, (int)(2 * i), H - 2 - b * (H - 4) / 255);
	}
}
static void screen_menu(void)
{
	static const char *const items[6] = { "SETPOINT", "LIMITS", "UNITS", "LOGGING", "CONTRAST", "ABOUT" };
	unsigned first = sel > 2u ? sel - 2u : 0u;
	for (unsigned i = 0; i < 3 && first + i < 6u; i++) {
		int inv = first + i == sel;
		if (inv) fb_fill(0, (int)(i * 10u + 1u), W, 9, 1);
		fb_text(4, (int)(i * 10u + 2u), items[first + i], inv);
		fb_num(110, (int)(i * 10u + 2u), (int32_t)(first + i + 1u), 1, inv);
	}
}
static void screen_stats(void)
{
	unsigned lo = 255, hi = 0, sum = 0;
	for (unsigned i = 0; i < 64; i++) { unsigned v = hist[i]; if (v < lo) lo = v; if (v > hi) hi = v; sum += v; }
	fb_text(2, 2, "MIN", 0); fb_num(26, 2, (int32_t)lo, 3, 0); fb_fill(50, 2, (int)(lo * 76u / 255u), 7, 1);
	fb_text(2, 12, "AVG", 0); fb_num(26, 12, (int32_t)(sum / 64u), 3, 0); fb_fill(50, 12, (int)(sum / 64u * 76u / 255u), 7, 1);
	fb_text(2, 22, "MAX", 0); fb_num(26, 22, (int32_t)hi, 3, 0); fb_fill(50, 22, (int)(hi * 76u / 255u), 7, 1);
}
static void screen_about(uint32_t ms)
{
	fb_text(2, 2, "RV328 DEMO", 0);
	fb_text(2, 12, "FW 1.0", 0); fb_num(50, 12, (int32_t)(ms & 0xffffu), 5, 0);
	fb_circle(108, 16, 12); fb_circle(108, 16, (int)(4u + ms / 4u % 8u));
	fb_line(108, 16, (int)(108u + ms % 12u), (int)(16u - ms / 2u % 12u));
}

static void display_init(void) { spi_begin(); }
static void display_step(unsigned pass, unsigned sample)
{
	uint32_t ms = millis();
	hist[hist_n++ % 64u] = (uint8_t)((sample >> 2) + (pass * 37u % 61u));
	buttons();
	sel = (uint8_t)(pass % 6u);
	memset(fb, 0, sizeof fb);
	switch (pass % 5u) {
	case 0: screen_home(ms); break;
	case 1: screen_graph(); break;
	case 2: screen_menu(); break;
	case 3: screen_stats(); break;
	default: screen_about(ms); break;
	}
	fb_flush();
}

#ifndef NO_MAIN
int main(void)
{
	hal_init();
	probe_begin();
	display_init();
	hal_set_input(0, 2500);
	for (unsigned pass = 0; pass < 5u * (ROUNDS + 1u); pass++) {
		if (pass == 5u) MARK(1, pass);
		display_step(pass, analog_read(0));
	}
	MARK(2, fb[100]);
	DONE();
}
#endif
