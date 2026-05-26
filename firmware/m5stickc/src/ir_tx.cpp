// Implementation of the baseband-IR transmitter. See ir_tx.h for
// the protocol-level contract.

#include "ir_tx.h"

#include <Arduino.h>

namespace opentama {

IRTx::IRTx(int ledPin, uint32_t baud)
    : _ledPin(ledPin), _bitMicros(1000000UL / baud) {}

void IRTx::begin() {
    pinMode(_ledPin, OUTPUT);
    digitalWrite(_ledPin, LOW);  // idle = LED off
}

void IRTx::send(const uint8_t* data, size_t len) {
    for (size_t i = 0; i < len; ++i) {
        sendByte(data[i]);
    }
}

void IRTx::sendByte(uint8_t b) {
    // We need fairly tight bit timing — disable interrupts for the
    // duration of one UART frame (10 bits at 9600 baud ≈ 1.04 ms).
    noInterrupts();

    // Start bit: mark (LED ON).
    digitalWrite(_ledPin, HIGH);
    delayMicroseconds(_bitMicros);

    // 8 data bits, LSB first. Bit value 1 => space (LED OFF),
    // bit value 0 => mark (LED ON).
    for (int i = 0; i < 8; ++i) {
        const bool one = (b >> i) & 0x1;
        digitalWrite(_ledPin, one ? LOW : HIGH);
        delayMicroseconds(_bitMicros);
    }

    // Stop bit: space (LED OFF).
    digitalWrite(_ledPin, LOW);
    delayMicroseconds(_bitMicros);

    interrupts();
}

}  // namespace opentama
