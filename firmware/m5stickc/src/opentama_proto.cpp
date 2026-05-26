// Implementation of the OpenTama wire protocol for the M5StickC.
// See opentama_proto.h for the layout; this file must stay byte-for-
// byte compatible with opentama/ir/protocol.py.

#include "opentama_proto.h"

#include <string.h>

namespace opentama {

uint16_t crc16(const uint8_t* data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; ++i) {
        crc ^= ((uint16_t)data[i]) << 8;
        for (int j = 0; j < 8; ++j) {
            if (crc & 0x8000) {
                crc = (uint16_t)((crc << 1) ^ 0x1021);
            } else {
                crc = (uint16_t)(crc << 1);
            }
        }
    }
    return crc;
}

size_t encodeFrame(
    uint8_t* out,
    size_t outSize,
    FrameType type,
    const uint8_t* payload,
    size_t payloadLen
) {
    if (payloadLen > MAX_PAYLOAD) {
        return 0;
    }
    const size_t total = HEADER_SIZE + payloadLen + CRC_SIZE;
    if (total > outSize) {
        return 0;
    }

    // Header: 'O' 'T' | version | type | payload_len (BE uint16)
    out[0] = MAGIC_0;
    out[1] = MAGIC_1;
    out[2] = VERSION;
    out[3] = (uint8_t)type;
    out[4] = (uint8_t)((payloadLen >> 8) & 0xFF);
    out[5] = (uint8_t)(payloadLen & 0xFF);

    if (payloadLen > 0 && payload != nullptr) {
        memcpy(out + HEADER_SIZE, payload, payloadLen);
    }

    const uint16_t crc = crc16(out, HEADER_SIZE + payloadLen);
    out[HEADER_SIZE + payloadLen]     = (uint8_t)((crc >> 8) & 0xFF);
    out[HEADER_SIZE + payloadLen + 1] = (uint8_t)(crc & 0xFF);

    return total;
}

// ---------------------------------------------------------------------
// Decoding
// ---------------------------------------------------------------------

ParsedFrame tryParseFrame(
    const uint8_t* buf,
    size_t len,
    size_t* consumed
) {
    ParsedFrame result;
    result.ok = false;
    result.type = HELLO;
    result.payload = nullptr;
    result.payloadLen = 0;
    *consumed = 0;

    if (buf == nullptr || len < HEADER_SIZE + CRC_SIZE) {
        // Not enough bytes for even an empty-payload frame; wait.
        return result;
    }

    // Scan for the MAGIC byte pair.
    size_t magicIdx = 0;
    bool   found    = false;
    while (magicIdx + 1 < len) {
        if (buf[magicIdx] == MAGIC_0 && buf[magicIdx + 1] == MAGIC_1) {
            found = true;
            break;
        }
        ++magicIdx;
    }
    if (!found) {
        // No magic anywhere — drop everything except the last byte,
        // which might be the start of an incoming MAGIC pair.
        *consumed = (len > 0) ? (len - 1) : 0;
        return result;
    }

    // Need at least a full header at magicIdx to read payload_len.
    if (len - magicIdx < HEADER_SIZE) {
        // Have a partial header; drop any garbage before magic so the
        // caller's buffer doesn't grow forever, but keep the partial.
        *consumed = magicIdx;
        return result;
    }

    const uint8_t* p          = buf + magicIdx;
    const uint8_t  version    = p[2];
    const uint8_t  type       = p[3];
    const uint16_t payloadLen = (uint16_t)((p[4] << 8) | p[5]);

    if (payloadLen > MAX_PAYLOAD) {
        // Garbage that happened to start with "OT". Skip past this
        // MAGIC and resync.
        *consumed = magicIdx + 2;
        return result;
    }
    if (version != VERSION) {
        *consumed = magicIdx + 2;
        return result;
    }

    const size_t total = HEADER_SIZE + payloadLen + CRC_SIZE;
    if (len - magicIdx < total) {
        // Have a header but not a complete payload + CRC yet — drop
        // the garbage prefix only.
        *consumed = magicIdx;
        return result;
    }

    const uint16_t expectedCRC = crc16(p, HEADER_SIZE + payloadLen);
    const uint16_t actualCRC   = (uint16_t)(
        ((uint16_t)p[HEADER_SIZE + payloadLen] << 8) |
        ((uint16_t)p[HEADER_SIZE + payloadLen + 1])
    );
    if (expectedCRC != actualCRC) {
        // CRC mismatch — could be a partial-frame collision with the
        // MAGIC bytes. Skip past this MAGIC and resync.
        *consumed = magicIdx + 2;
        return result;
    }

    // Success.
    result.ok         = true;
    result.type       = (FrameType)type;
    result.payload    = p + HEADER_SIZE;
    result.payloadLen = payloadLen;
    *consumed         = magicIdx + total;
    return result;
}

}  // namespace opentama
