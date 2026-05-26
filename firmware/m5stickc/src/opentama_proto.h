// OpenTama IR wire-protocol — C++ port for the M5StickC firmware.
//
// Byte-for-byte identical to opentama/ir/protocol.py. The Python
// decoder must be able to ingest whatever encodeFrame() produces here,
// and vice versa.
//
// Frame layout (big-endian throughout):
//
//   +---------+---------+--------+------------------+---------+--------+
//   | magic   | version | type   | payload length   | payload | crc16  |
//   | 2 bytes | 1 byte  | 1 byte | 2 bytes (uint16) | N bytes | 2 bytes|
//   +---------+---------+--------+------------------+---------+--------+
//
// CRC-16/CCITT-FALSE (poly=0x1021, init=0xFFFF) over magic..payload.

#pragma once

#include <stddef.h>
#include <stdint.h>

namespace opentama {

constexpr uint8_t MAGIC_0 = 'O';
constexpr uint8_t MAGIC_1 = 'T';
constexpr uint8_t VERSION = 1;
constexpr size_t HEADER_SIZE = 6;
constexpr size_t CRC_SIZE = 2;
constexpr size_t MAX_PAYLOAD = 1024;

enum FrameType : uint8_t {
    HELLO = 1,
    STATE = 2,
    GIFT  = 3,
    VISIT = 4,
    ACK   = 5,
};

// CRC-16/CCITT-FALSE (poly=0x1021, init=0xFFFF), exactly matching
// opentama.ir.protocol.crc16 on the Python side.
uint16_t crc16(const uint8_t* data, size_t len);

// Encode a single frame into ``out``. Returns the number of bytes
// written, or 0 if the buffer is too small or the payload is over
// MAX_PAYLOAD. The minimum buffer size needed is
// ``HEADER_SIZE + payloadLen + CRC_SIZE``.
size_t encodeFrame(
    uint8_t* out,
    size_t outSize,
    FrameType type,
    const uint8_t* payload,
    size_t payloadLen
);

}  // namespace opentama
