// IR receive module for the M5StickC.
//
// Reads UART-style bytes from an external IR receiver unit connected
// to one of the Grove pins (or any free GPIO). This is the symmetric
// counterpart of ir_tx.h: where TX bit-bangs the built-in IR LED,
// RX delegates to the ESP32's hardware UART (Serial1) bound to a
// single RX pin so we don't burn cycles bit-banging at every poll.
//
// Wiring (M5StickC Plus2 default):
//
//   IR Receiver Unit -- Grove cable -- M5StickC Plus2 Grove port
//                                       ├─ Vcc (3.3 V)
//                                       ├─ GND
//                                       └─ Data --> GPIO 33 (configurable
//                                                            via
//                                                            OPENTAMA_IR_RX_PIN)
//
// The receiver unit is expected to emit baseband UART (start bit /
// 8 data bits / stop bit, 9600 baud, polarity matching ir_tx.h —
// "mark = LED on at the transmitter = logical 0 on the wire"). This
// is what TFDU4101 / TFDU6102-class IR-UART transceivers do natively.
// Remote-control style receivers (TSOP4838 etc.) need a demodulation
// layer in front; see README.md.

#pragma once

#include <stddef.h>
#include <stdint.h>

namespace opentama {

class IRRx {
public:
    // `rxPin` is the GPIO connected to the IR receiver's data line.
    // `baud` is the UART baud rate; keep it in sync with ir_tx.
    IRRx(int rxPin, uint32_t baud = 9600);

    // Initialise Serial1 against the configured pin. Call once from
    // setup(). Idempotent — calling twice rebinds Serial1.
    void begin();

    // Number of bytes already buffered by the hardware UART driver.
    int available();

    // Pull up to ``n`` bytes from the UART buffer into ``buf``.
    // Returns the number of bytes actually read.
    size_t read(uint8_t* buf, size_t n);

private:
    int      _rxPin;
    uint32_t _baud;
};

}  // namespace opentama
