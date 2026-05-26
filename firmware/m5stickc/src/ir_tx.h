// Baseband-IR transmit module for the M5StickC.
//
// Drives the built-in IR LED with a UART-style bit stream at a
// configurable baud rate. This is the simplest possible IR transport:
// it matches what a TFDU4101 / TFDU6102-class IR-UART transceiver
// expects on the line. It will *not* talk to a 38 kHz remote-control
// receiver (TSOP4838 etc.) without an extra modulation layer; for that
// path see the README's "physical layer" section.
//
// Conventions used here:
//   - Idle state of the IR LED is OFF (digital LOW on a high-side
//     driven LED, which is the M5StickC layout).
//   - "Mark" bit (logical 0)  -> LED ON.
//   - "Space" bit (logical 1) -> LED OFF.
//   - Each UART frame is start bit (mark) | 8 data bits LSB-first |
//     stop bit (space). No parity.
//
// This inverts polarity relative to a raw RS-232 line, matching IrDA
// SIR conventions ("LED on = logical 0"). The Python `SerialIRTransport`
// on the other end is told the same baud rate and reads bytes verbatim.

#pragma once

#include <stddef.h>
#include <stdint.h>

namespace opentama {

class IRTx {
public:
    // ``ledPin`` is the GPIO that drives the IR LED. ``baud`` is the
    // UART baud rate; 9600 is a good default and is what the existing
    // Python `SerialIRTransport.DEFAULT_BAUDRATE` uses.
    IRTx(int ledPin, uint32_t baud = 9600);

    // Initialise the GPIO. Call once from setup().
    void begin();

    // Send ``len`` raw bytes out the LED. Blocks until done. Disables
    // interrupts around each bit window to keep timing tight on the
    // ESP32 (USB serial and WiFi tasks can otherwise insert jitter).
    void send(const uint8_t* data, size_t len);

private:
    void sendByte(uint8_t b);

    int      _ledPin;
    uint32_t _bitMicros;  // microseconds per UART bit
};

}  // namespace opentama
