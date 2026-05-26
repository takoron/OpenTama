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

static constexpr uint32_t HELLO_INTERVAL_MS = 5000;
static constexpr uint32_t FLASH_DURATION_MS = 400;

// ---------------------------------------------------------------------
// Globals
// ---------------------------------------------------------------------

static opentama::IRTx irTx(OPENTAMA_IR_LED_PIN, 9600);
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
// Arduino entry points
// ---------------------------------------------------------------------

void setup() {
    auto cfg = M5.config();
    M5.begin(cfg);
    M5.Display.setRotation(3);
    drawStaticUI();

    irTx.begin();

    Serial.begin(115200);
    delay(100);
    Serial.printf("OpenTama M5StickC firmware boot — pet=%s stage=%s gp=%u\n",
                  OPENTAMA_PET_NAME, OPENTAMA_PET_STAGE,
                  (unsigned)OPENTAMA_PET_GP);
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

    clearFlashIfDue();
    delay(10);
}
