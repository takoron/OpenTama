// OpenTama firmware for the M5StickC Plus2.
//
// Behaviour:
//   * Boots into a ガラケー-style "screen" showing the pet name and
//     stage.
//   * Every HELLO_INTERVAL_MS the stick blinks an OpenTama HELLO
//     frame out the IR LED. A nearby OpenTama running
//     `python -m opentama proximity scan` will log the sighting.
//   * Button A (front) sends a GIFT frame.
//   * Button B (side)  sends a VISIT frame.
//   * The LCD briefly flashes the action so you know it fired.
//
// The pet identity is compile-time configurable via the
// OPENTAMA_PET_NAME / OPENTAMA_PET_STAGE / OPENTAMA_PET_GP macros in
// platformio.ini. Changing those and re-flashing is the easiest way
// to give each colleague's stick a distinct identity.

#include <M5Unified.h>
#include <stdio.h>
#include <string.h>

#include "ir_rx.h"
#include "ir_tx.h"
#include "opentama_proto.h"

// ---------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------

#ifndef OPENTAMA_PET_NAME
#define OPENTAMA_PET_NAME "たころん"
#endif
#ifndef OPENTAMA_PET_STAGE
#define OPENTAMA_PET_STAGE "child"
#endif
#ifndef OPENTAMA_PET_GP
#define OPENTAMA_PET_GP 60
#endif

// M5StickC Plus2 has its IR LED on GPIO19. Older M5StickC: GPIO9.
// Override if you wired up a different LED.
#ifndef OPENTAMA_IR_LED_PIN
#define OPENTAMA_IR_LED_PIN 19
#endif

// GPIO connected to the external IR receiver unit (Grove cable on
// M5StickC Plus2's Grove port → G33). Set to -1 to disable RX
// (transmit-only build).
#ifndef OPENTAMA_IR_RX_PIN
#define OPENTAMA_IR_RX_PIN 33
#endif

static constexpr uint32_t HELLO_INTERVAL_MS = 5000;
static constexpr uint32_t FLASH_DURATION_MS = 400;
static constexpr size_t   RX_BUFFER_SIZE    = 1024;  // headroom for a few stacked frames

// ---------------------------------------------------------------------
// Globals
// ---------------------------------------------------------------------

static opentama::IRTx irTx(OPENTAMA_IR_LED_PIN, 9600);
#if OPENTAMA_IR_RX_PIN >= 0
static opentama::IRRx irRx(OPENTAMA_IR_RX_PIN, 9600);
#endif

static uint8_t  rxBuffer[RX_BUFFER_SIZE];
static size_t   rxLen        = 0;       // bytes currently in rxBuffer
static char     lastPeerName[64] = {0};
static uint32_t lastPeerAt   = 0;
static uint32_t peersSeen    = 0;       // lifetime counter for the LCD

static uint32_t lastHelloAt = 0;
static uint32_t flashUntil = 0;

// ---------------------------------------------------------------------
// LCD layout (ガラケー-ish)
// ---------------------------------------------------------------------

static void drawStaticUI() {
    M5.Display.fillScreen(BLACK);

    // Top banner — black-on-green "carrier label", in homage to a flip
    // phone's network indicator strip.
    M5.Display.fillRect(0, 0, M5.Display.width(), 20, DARKGREEN);
    M5.Display.setTextColor(BLACK, DARKGREEN);
    M5.Display.setTextSize(1);
    M5.Display.setCursor(4, 6);
    M5.Display.printf("OpenTama IR  *");

    // Pet name + stage as the "wallpaper".
    M5.Display.setTextColor(GREEN, BLACK);
    M5.Display.setTextSize(2);
    M5.Display.setCursor(8, 36);
    M5.Display.printf("%s", OPENTAMA_PET_NAME);

    M5.Display.setTextSize(1);
    M5.Display.setTextColor(LIGHTGREY, BLACK);
    M5.Display.setCursor(8, 64);
    M5.Display.printf("%s  %u gp", OPENTAMA_PET_STAGE, (unsigned)OPENTAMA_PET_GP);

    // Footer hint.
    M5.Display.setTextColor(DARKGREY, BLACK);
    M5.Display.setCursor(4, M5.Display.height() - 12);
    M5.Display.printf("A:GIFT  B:VISIT");

    // Reserve the "RX strip" area in advance so flash messages don't
    // overlap it. We draw the actual last-peer text from updateRxStrip().
}

static void updateRxStrip() {
    // Bottom-of-screen line above the footer that always shows the
    // most recent peer we received over IR.
    const int y = M5.Display.height() - 26;
    M5.Display.fillRect(0, y, M5.Display.width(), 12, BLACK);
    if (lastPeerName[0] == 0) {
        M5.Display.setTextColor(DARKGREY, BLACK);
        M5.Display.setCursor(4, y + 2);
        M5.Display.setTextSize(1);
        M5.Display.printf("RX: (waiting)");
        return;
    }
    M5.Display.setTextColor(YELLOW, BLACK);
    M5.Display.setCursor(4, y + 2);
    M5.Display.setTextSize(1);
    M5.Display.printf("RX: %s (#%u)", lastPeerName, (unsigned)peersSeen);
}

static void flashMessage(const char* msg, uint16_t color) {
    M5.Display.fillRect(0, 90, M5.Display.width(), 24, color);
    M5.Display.setTextColor(BLACK, color);
    M5.Display.setTextSize(2);
    M5.Display.setCursor(8, 94);
    M5.Display.printf("%s", msg);
    flashUntil = millis() + FLASH_DURATION_MS;
}

static void clearFlashIfDue() {
    if (flashUntil != 0 && millis() >= flashUntil) {
        M5.Display.fillRect(0, 90, M5.Display.width(), 24, BLACK);
        flashUntil = 0;
    }
}

// ---------------------------------------------------------------------
// Frame senders
// ---------------------------------------------------------------------

static void sendFrame(opentama::FrameType type, const char* json) {
    uint8_t buf[256];
    const size_t total = opentama::encodeFrame(
        buf, sizeof(buf),
        type,
        reinterpret_cast<const uint8_t*>(json),
        strlen(json)
    );
    if (total == 0) {
        Serial.println("encode failed (buffer too small / payload too large)");
        return;
    }
    irTx.send(buf, total);

    // Log to USB serial for sanity-checking on the bench.
    Serial.printf("TX %u bytes (type=%u): %s\n",
                  (unsigned)total, (unsigned)type, json);
}

static void sendHello() {
    char json[160];
    snprintf(json, sizeof(json),
             "{\"name\":\"%s\",\"stage\":\"%s\",\"gp\":%u}",
             OPENTAMA_PET_NAME, OPENTAMA_PET_STAGE,
             (unsigned)OPENTAMA_PET_GP);
    sendFrame(opentama::HELLO, json);
    flashMessage("HELLO", CYAN);
}

static void sendGift() {
    char json[128];
    snprintf(json, sizeof(json),
             "{\"kind\":\"food\",\"from\":\"%s\"}",
             OPENTAMA_PET_NAME);
    sendFrame(opentama::GIFT, json);
    flashMessage("GIFT", GREEN);
}

static void sendVisit() {
    char json[128];
    snprintf(json, sizeof(json),
             "{\"from\":\"%s\"}", OPENTAMA_PET_NAME);
    sendFrame(opentama::VISIT, json);
    flashMessage("VISIT", MAGENTA);
}

// ---------------------------------------------------------------------
// Receive path
// ---------------------------------------------------------------------

// Pull the value of a top-level JSON string key out of ``payload``,
// without bringing in a full JSON parser. Looks for a sequence of the
// form ``"<key>":"<value>"`` and copies ``<value>`` into ``out``
// (NUL-terminated, truncated to ``outSize - 1`` bytes). Returns true
// on success.
//
// This is intentionally narrow: the only payloads we ever decode here
// are the tiny ones the protocol itself defines (HELLO/STATE: name;
// GIFT/VISIT: from). It does not handle escapes, nested objects, or
// non-string values — those don't appear in any of our frames.
static bool extractJsonString(
    const uint8_t* payload,
    size_t         payloadLen,
    const char*    key,
    char*          out,
    size_t         outSize
) {
    if (outSize == 0) return false;
    out[0] = 0;

    // Build the search needle: "<key>"
    char needle[48];
    int  n = snprintf(needle, sizeof(needle), "\"%s\"", key);
    if (n < 0 || (size_t)n >= sizeof(needle)) return false;

    // Locate the needle inside payload.
    for (size_t i = 0; i + (size_t)n <= payloadLen; ++i) {
        if (memcmp(payload + i, needle, (size_t)n) != 0) continue;
        // Skip key, then optional whitespace and ':'.
        size_t j = i + (size_t)n;
        while (j < payloadLen && (payload[j] == ' ' || payload[j] == '\t')) ++j;
        if (j >= payloadLen || payload[j] != ':') continue;
        ++j;
        while (j < payloadLen && (payload[j] == ' ' || payload[j] == '\t')) ++j;
        if (j >= payloadLen || payload[j] != '"') continue;
        ++j;
        // Copy until the closing quote.
        size_t k = 0;
        while (j < payloadLen && payload[j] != '"' && k + 1 < outSize) {
            out[k++] = (char)payload[j++];
        }
        out[k] = 0;
        return true;
    }
    return false;
}

static const char* frameTypeName(opentama::FrameType t) {
    switch (t) {
        case opentama::HELLO: return "HELLO";
        case opentama::STATE: return "STATE";
        case opentama::GIFT:  return "GIFT";
        case opentama::VISIT: return "VISIT";
        case opentama::ACK:   return "ACK";
        default:              return "?";
    }
}

static void rememberPeer(const char* name) {
    if (!name || !*name) return;
    strncpy(lastPeerName, name, sizeof(lastPeerName) - 1);
    lastPeerName[sizeof(lastPeerName) - 1] = 0;
    lastPeerAt = millis();
    ++peersSeen;
    updateRxStrip();
    flashMessage("RX", YELLOW);
}

static void onFrameReceived(const opentama::ParsedFrame& f) {
    char name[64];
    bool gotName = false;
    if (f.type == opentama::HELLO || f.type == opentama::STATE) {
        gotName = extractJsonString(
            f.payload, f.payloadLen, "name", name, sizeof(name)
        );
    } else if (f.type == opentama::GIFT || f.type == opentama::VISIT) {
        gotName = extractJsonString(
            f.payload, f.payloadLen, "from", name, sizeof(name)
        );
    }

    if (gotName) {
        rememberPeer(name);
        Serial.printf("RX %s from %s (%u B payload)\n",
                      frameTypeName(f.type), name, (unsigned)f.payloadLen);
    } else {
        // ACK or a frame we can't extract a name from — log but don't
        // flash a peer.
        Serial.printf("RX %s (%u B payload, no peer id)\n",
                      frameTypeName(f.type), (unsigned)f.payloadLen);
    }
}

static void serviceReceive() {
#if OPENTAMA_IR_RX_PIN < 0
    return;  // RX disabled at compile time
#else
    if (irRx.available() <= 0) return;

    // Drain whatever the UART driver has buffered into our rxBuffer.
    while (rxLen < RX_BUFFER_SIZE && irRx.available() > 0) {
        const size_t freeSpace = RX_BUFFER_SIZE - rxLen;
        const size_t n = irRx.read(rxBuffer + rxLen, freeSpace);
        if (n == 0) break;
        rxLen += n;
    }
    if (rxLen == RX_BUFFER_SIZE) {
        // Buffer full and the parser couldn't keep up — drop the
        // front half so a noisy line can't permanently wedge us.
        memmove(rxBuffer, rxBuffer + (RX_BUFFER_SIZE / 2),
                RX_BUFFER_SIZE / 2);
        rxLen = RX_BUFFER_SIZE / 2;
    }

    // Parse as many complete frames as we can out of rxBuffer.
    while (rxLen >= opentama::HEADER_SIZE + opentama::CRC_SIZE) {
        size_t consumed = 0;
        opentama::ParsedFrame f =
            opentama::tryParseFrame(rxBuffer, rxLen, &consumed);
        if (consumed == 0 && !f.ok) {
            // Parser is telling us "need more bytes, nothing to drop".
            break;
        }
        if (f.ok) {
            onFrameReceived(f);
        }
        if (consumed > 0 && consumed <= rxLen) {
            memmove(rxBuffer, rxBuffer + consumed, rxLen - consumed);
            rxLen -= consumed;
        } else {
            break;  // safety
        }
    }
#endif
}

// ---------------------------------------------------------------------
// Arduino entry points
// ---------------------------------------------------------------------

void setup() {
    auto cfg = M5.config();
    M5.begin(cfg);
    M5.Display.setRotation(3);
    drawStaticUI();
    updateRxStrip();

    irTx.begin();
#if OPENTAMA_IR_RX_PIN >= 0
    irRx.begin();
#endif

    Serial.begin(115200);
    delay(100);
    Serial.printf("OpenTama M5StickC firmware boot — pet=%s stage=%s gp=%u "
                  "tx_pin=%d rx_pin=%d\n",
                  OPENTAMA_PET_NAME, OPENTAMA_PET_STAGE,
                  (unsigned)OPENTAMA_PET_GP,
                  (int)OPENTAMA_IR_LED_PIN, (int)OPENTAMA_IR_RX_PIN);
}

void loop() {
    M5.update();
    const uint32_t now = millis();

    if (now - lastHelloAt > HELLO_INTERVAL_MS) {
        sendHello();
        lastHelloAt = now;
    }
    if (M5.BtnA.wasPressed()) {
        sendGift();
    }
    if (M5.BtnB.wasPressed()) {
        sendVisit();
    }

    serviceReceive();

    clearFlashIfDue();
    delay(10);
}
