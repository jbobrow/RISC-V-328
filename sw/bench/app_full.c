/* Benchmark "full": the three programs above as one firmware, the size of a
 * typical complete project on this class of chip. Each pass of the main loop
 * runs the sensor/PID/log step (log lines go to a card on the SPI bus), redraws
 * one display screen and serves the serial protocol; one request arrives per pass. */
#define NO_MAIN
/* the serial port carries the protocol here, so the log line goes to a card on the SPI bus */
static void card_log(const char *s);
#define LOG_OUT card_log
#include "app_logger.c"
#include "app_display.c"
#include "app_comms.c"
static void card_log(const char *s)
{
	pin_cs(1, 0);
	while (*s) spi_write((uint8_t)*s++);
	pin_cs(1, 1);
}
#define FWARM 10u
#define FRUN  30u

int main(void)
{
	hal_init();
	serial_begin(115200);
	probe_begin();
	display_init();
	comms_init();
	for (unsigned pass = 0; pass < FWARM + FRUN; pass++) {
		if (pass == FWARM) MARK(1, pass);
		comms_master(FWARM + FRUN);
		logger_step(pass);
		while (comms_slave()) ;
		display_step(pass, (unsigned)filt * 8u);
		while (comms_slave()) ;
	}
	for (unsigned idle = 0; idle < 4000u; idle++) if (comms_slave()) idle = 0;
	MARK(2, ok_frames);
	MARK(3, overruns);
	MARK(4, bad_crc);
	MARK(5, rx_bytes);
	DONE();
}
