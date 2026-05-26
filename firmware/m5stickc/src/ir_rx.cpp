// Implementation of the IR receive module. See ir_rx.h for wiring +
// the UART polarity contract.

#include "ir_rx.h"

#include <Arduino.h>

namespace opentama {

IRRx::IRRx(int rxPin, uint32_t baud)
    : _rxPin(rxPin), _baud(baud) {}

void IRRx::begin() {
    // Use Serial1 (ESP32 UART1) so we don't fight USB serial logging
    // on Serial0. tx=-1 disables TX on this port; the IR LED is
    // bit-banged separately by IRTx and shouldn't share a UART with
    // the receiver pin.
    Serial1.begin(_baud, SERIAL_8N1, _rxPin, /*tx=*/-1);
}

int IRRx::available() {
    return Serial1.available();
}

size_t IRRx::read(uint8_t* buf, size_t n) {
    size_t i = 0;
    while (i < n && Serial1.available()) {
        const int b = Serial1.read();
        if (b < 0) {
            break;
        }
        buf[i++] = (uint8_t)b;
    }
    return i;
}

}  // namespace opentama
