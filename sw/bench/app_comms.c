/* Benchmark "comms": a Modbus-RTU style slave. Requests arrive back to back at
 * 115200 baud on the second serial port (receive interrupt into a ring buffer); the main loop
 * parses them, checks the CRC, runs one of six handlers and builds the reply.
 * The requests come from this program's own USART0 (wiring 1: TXD0 -> RXD1),
 * standing in for the bus master. The verdict is how many frames were answered
 * and how many bytes the receiver lost (overrun). */
#include <string.h>
#include "hal.h"
#define FRAMES 60u
#define RXBUF 64u
static volatile uint8_t rxb[RXBUF];
static volatile uint8_t rx_h, rx_t;
static volatile uint32_t overruns, rx_bytes;
static uint16_t reg[16];
static uint32_t ok_frames, bad_crc, exceptions;
static uint8_t reply[40];

HAL_ISR static void link_rx(uint8_t d, unsigned overrun)
{
	if (overrun) overruns++;
	uint8_t n = (uint8_t)((rx_h + 1u) % RXBUF);
	if (n != rx_t) { rxb[rx_h] = d; rx_h = n; } else overruns++;
	rx_bytes++;
}
static uint16_t crc16(const uint8_t *p, unsigned n)
{
	uint16_t c = 0xFFFFu;
	while (n--) {
		c ^= *p++;
		for (unsigned i = 0; i < 8; i++) c = (c & 1u) ? (uint16_t)((c >> 1) ^ 0xA001u) : (uint16_t)(c >> 1);
	}
	return c;
}
static unsigned finish(uint8_t *f, unsigned n) { uint16_t c = crc16(f, n); f[n] = (uint8_t)c; f[n + 1] = (uint8_t)(c >> 8); return n + 2u; }
static unsigned exception(const uint8_t *q, uint8_t code)
{
	exceptions++;
	reply[0] = q[0]; reply[1] = q[1] | 0x80u; reply[2] = code;
	return finish(reply, 3);
}
static unsigned h_read(const uint8_t *q, int input)
{
	unsigned a = (unsigned)(q[2] << 8 | q[3]), n = (unsigned)(q[4] << 8 | q[5]);
	if (n == 0 || n > 8u) return exception(q, 3);
	if (a + n > 16u) return exception(q, 2);
	reply[0] = q[0]; reply[1] = q[1]; reply[2] = (uint8_t)(2u * n);
	for (unsigned i = 0; i < n; i++) {
		uint16_t v = input ? (uint16_t)(reg[a + i] ^ 0x5A5Au) : reg[a + i];
		reply[3 + 2 * i] = (uint8_t)(v >> 8); reply[4 + 2 * i] = (uint8_t)v;
	}
	return finish(reply, 3u + 2u * n);
}
static unsigned h_write1(const uint8_t *q)
{
	unsigned a = (unsigned)(q[2] << 8 | q[3]);
	if (a >= 16u) return exception(q, 2);
	reg[a] = (uint16_t)(q[4] << 8 | q[5]);
	memcpy(reply, q, 6);
	return finish(reply, 6);
}
static unsigned h_writen(const uint8_t *q)
{
	unsigned a = (unsigned)(q[2] << 8 | q[3]), n = (unsigned)(q[4] << 8 | q[5]);
	if (n == 0 || n > 4u || q[6] != 2u * n) return exception(q, 3);
	if (a + n > 16u) return exception(q, 2);
	for (unsigned i = 0; i < n; i++) reg[a + i] = (uint16_t)(q[7 + 2 * i] << 8 | q[8 + 2 * i]);
	memcpy(reply, q, 6);
	return finish(reply, 6);
}
static unsigned h_diag(const uint8_t *q)
{
	unsigned sub = (unsigned)(q[2] << 8 | q[3]);
	memcpy(reply, q, 6);
	if (sub == 0x000Bu) { reply[4] = (uint8_t)(ok_frames >> 8); reply[5] = (uint8_t)ok_frames; }
	else if (sub == 0x000Cu) { reply[4] = (uint8_t)(bad_crc >> 8); reply[5] = (uint8_t)bad_crc; }
	else if (sub != 0u) return exception(q, 1);
	return finish(reply, 6);
}
static unsigned h_ident(const uint8_t *q)
{
	static const char id[] = "RV328 gateway 1.0";
	reply[0] = q[0]; reply[1] = q[1]; reply[2] = (uint8_t)(sizeof id + 1u); reply[3] = 0x28;
	memcpy(reply + 4, id, sizeof id - 1u); reply[3 + sizeof id] = 0xFF;
	return finish(reply, 4u + sizeof id);
}

/* request length from the function code (and the byte count for 0x10) */
static unsigned frame_len(const uint8_t *q, unsigned have)
{
	if (have < 2u) return 0;
	switch (q[1]) {
	case 0x03: case 0x04: case 0x06: case 0x08: return 8;
	case 0x10: return have < 7u ? 0 : 9u + q[6];
	case 0x11: return 4;
	default: return 4;
	}
}
static unsigned dispatch(const uint8_t *q)
{
	switch (q[1]) {
	case 0x03: return h_read(q, 0);
	case 0x04: return h_read(q, 1);
	case 0x06: return h_write1(q);
	case 0x08: return h_diag(q);
	case 0x10: return h_writen(q);
	case 0x11: return h_ident(q);
	default: return exception(q, 1);
	}
}

/* the "bus master": next request, queued only when the whole frame fits in the transmit ring */
static unsigned make_request(uint8_t *f, unsigned k)
{
	f[0] = 0x11;
	switch (k % 6u) {
	case 0: f[1] = 0x03; f[2] = 0; f[3] = (uint8_t)(k % 9u); f[4] = 0; f[5] = (uint8_t)(1u + k % 7u); return finish(f, 6);
	case 1: f[1] = 0x06; f[2] = 0; f[3] = (uint8_t)(k % 16u); f[4] = (uint8_t)k; f[5] = (uint8_t)(k * 7u); return finish(f, 6);
	case 2: f[1] = 0x04; f[2] = 0; f[3] = (uint8_t)(k % 12u); f[4] = 0; f[5] = (uint8_t)(1u + k % 4u); return finish(f, 6);
	case 3: f[1] = 0x10; f[2] = 0; f[3] = (uint8_t)(k % 13u); f[4] = 0; f[5] = 2; f[6] = 4;
	        f[7] = (uint8_t)k; f[8] = 1; f[9] = 2; f[10] = (uint8_t)(k >> 1); return finish(f, 11);
	case 4: f[1] = 0x08; f[2] = 0; f[3] = (uint8_t)(k % 3u == 0u ? 0x0B : 0x00); f[4] = 0xA5; f[5] = 0x37; return finish(f, 6);
	default: f[1] = 0x11; return finish(f, 2);
	}
}

static uint8_t q[24], out[16];
static unsigned have, sent, olen;

static void comms_init(void) { link_begin(link_rx); }
/* master side: queue the next request once the whole frame fits in the transmit ring */
static void comms_master(unsigned frames)
{
	if (sent >= frames) return;
	if (olen == 0) olen = make_request(out, sent);
	if (serial_tx_free() >= olen) { for (unsigned i = 0; i < olen; i++) serial_write(out[i]); olen = 0; sent++; }
}
/* slave side: take one received byte; returns 0 when the ring is empty */
static int comms_slave(void)
{
	if (rx_h == rx_t) return 0;
	q[have++] = rxb[rx_t]; rx_t = (uint8_t)((rx_t + 1u) % RXBUF);
	unsigned need = frame_len(q, have);
	if (need && have >= need) {
		if (crc16(q, need) == 0u && q[0] == 0x11u) { ok_frames++; (void)dispatch(q); }
		else { bad_crc++; }
		have = 0;
	}
	if (have >= sizeof q) have = 0;
	return 1;
}

#ifndef NO_MAIN
int main(void)
{
	unsigned idle = 0;
	uint32_t status_at = 0;

	hal_init();
	serial_begin(115200);
	comms_init();
	hal_set_input(0, 1800);
	MARK(1, 0);
	while (idle < 4000u) {
		comms_master(FRAMES);
		if (comms_slave()) idle = 0; else if (sent >= FRAMES) idle++;
		/* application side: refresh two input registers from the ADC a few times a second */
		uint32_t now = millis();
		if (now - status_at >= 3u) {
			status_at = now;
			reg[14] = analog_read(0); reg[15] = (uint16_t)now;
		}
	}
	MARK(2, ok_frames);
	MARK(3, overruns);
	MARK(4, bad_crc);
	MARK(5, rx_bytes);
	DONE();
}
#endif
