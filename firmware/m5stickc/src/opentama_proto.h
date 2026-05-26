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

// ---------------------------------------------------------------------
// Decoding (counterpart of opentama.ir.protocol.parse_stream in Python)
// ---------------------------------------------------------------------

struct ParsedFrame {
    bool        ok;          // true iff a complete, valid frame was extracted
    FrameType   type;
    const uint8_t* payload;  // borrowed pointer into the caller's buffer
    size_t      payloadLen;
};

// Try to extract one OpenTama frame from the front of ``buf``.
//
// On return:
//   - ``ParsedFrame.ok == true``  → a complete frame was found at
//     offset (``*consumed`` - frame total). The ``payload`` pointer is
//     borrowed from ``buf`` and is only valid until the caller mutates
//     ``buf``.
//   - ``ParsedFrame.ok == false`` → no complete valid frame in ``buf``
//     **yet**. ``*consumed`` is set to the number of bytes the caller
//     should drop from the front of ``buf`` before the next call:
//       * zero if we need more bytes
//       * non-zero to skip past garbage / a bad-CRC frame / a wrong-
//         version frame, retaining whatever might be a real partial
//         frame at the tail.
//
// This is the C++ mirror of ``opentama.ir.protocol.parse_stream``: it
// implements the same MAGIC resync, CRC-16/CCITT-FALSE check, and
// version gate. The PC running ``proximity scan`` and the stick
// running this firmware therefore agree on what counts as a frame.
ParsedFrame tryParseFrame(
    const uint8_t* buf,
    size_t len,
    size_t* consumed
);

}  // namespace opentama
