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

}  // namespace opentama
