# OpenTama M5StickC firmware — "ガラケー赤外線たまごっち"

A tiny ESP32 firmware that turns an [M5StickC Plus2](https://docs.m5stack.com/en/core/M5StickC%20PLUS2)
into a physical OpenTama pet that periodically introduces itself over
its built-in IR LED. Pair two of them — or pair one with a PC running
`python -m opentama proximity scan` — and you have a literal
赤外線たまごっち sitting on your desk.

## What it does (today)

- Boots into a ガラケー-style LCD screen: a top "carrier strip",
  the pet's name in big text, stage + growth points underneath, and
  a button-hint footer.
- Every **5 seconds**, blinks an OpenTama `HELLO` frame out the IR LED
  carrying `{name, stage, gp}`. The LCD flashes "HELLO" so you can see
  the ping.
- **Button A** (front) sends a `GIFT` frame (`{kind:"food", from:<name>}`).
- **Button B** (side) sends a `VISIT` frame (`{from:<name>}`).
- USB serial (115200 baud) prints every transmitted frame as
  `TX N bytes (type=…): {json}` for bench debugging.

Frames are byte-for-byte identical to what `opentama/ir/protocol.py`
produces. A PC running `python -m opentama proximity scan --port
serial:///dev/ttyUSB0` will receive `HELLO`/`GIFT`/`VISIT` from the
stick and append `PeerSighting` records to
`~/.opentama/proximity.jsonl`. From there, the existing pipeline takes
over: `proximity digest --notify-teams` summarises and posts to Teams.

## What it does *not* do (yet)

- **No receive.** The Plus2 ships with an IR LED but no IR
  photodiode, so the firmware can transmit but not listen. To detect a
  peer's transmissions you need either a PC with a USB-IR adapter, or
  a second stick equipped with an [M5StickC IR Unit / IR Hat](https://docs.m5stack.com/en/unit/ir).
- **No state sync from PC.** Pet name / stage / gp are compile-time
  constants set by `OPENTAMA_PET_NAME` / `OPENTAMA_PET_STAGE` /
  `OPENTAMA_PET_GP` in `platformio.ini`. Re-flash to change them.
- **No power management.** It just hellos every 5 seconds forever.
  Workable on USB-C power; the 200 mAh battery will not last a day
  with the current duty cycle.

These are all explicit follow-up scope, not bugs.

## Parts

| What | Why | Approx. cost |
|---|---|---|
| M5StickC Plus2 (or original M5StickC) | The brain + LCD + IR LED + 2 buttons. | ¥3,000 |
| USB-C cable | Power + flashing. | already have it |
| (optional) USB-IR adapter on the receiving PC | Lets a PC pick up the stick's transmissions and feed them into `proximity scan`. Look for "SIR" / "9600 baud" / "TFDU"-class adapters. | ¥1,500–¥3,000 |
| (optional) M5StickC IR Unit on a second stick | Lets a *second* stick listen for the first. Not implemented in this firmware yet. | ¥800 |

## Pinout

M5StickC Plus2 has the IR LED on **GPIO 19**. The original M5StickC
puts it on **GPIO 9**. The firmware defaults to GPIO 19 but you can
override at build time:

```bash
pio run -e m5stick-c-plus2 -e custom -DOPENTAMA_IR_LED_PIN=9
```

(or just edit `OPENTAMA_IR_LED_PIN` in `src/main.cpp`).

## Physical-layer caveats

The firmware drives the IR LED with a **baseband UART bit stream** at
9600 baud — start bit (LED on), 8 data bits LSB-first (1 = LED off,
0 = LED on), stop bit (LED off). This matches what an
**IR-UART transceiver** (TFDU4101, TFDU6102, IrDA SIR-compatible) on
the receiving side expects.

It will **not** drive a 38 kHz remote-control IR receiver
(TSOP4838 etc.) correctly without an extra modulation layer wrapping
each "mark" bit in a 38 kHz burst. If your receive path is a
remote-control receiver, you have three options:

1. Use a real IR-UART receiver instead (recommended).
2. Modify `ir_tx.cpp:sendByte` to bit-bang a 38 kHz burst for each
   "mark" sub-period.
3. Swap to one of the Arduino IR-remote libraries (e.g. IRremoteESP8266)
   and a custom carrier protocol — but then the PC side also needs to
   demodulate, which is more work than it's worth for this PoC.

## Build & flash

```bash
# In firmware/m5stickc/
pio run -e m5stick-c-plus2
pio run -e m5stick-c-plus2 -t upload
pio device monitor -b 115200   # optional: watch TX log
```

Connect the stick over USB-C and hold the side button while plugging
in if your board needs the bootloader pin. The Plus2 normally just
takes the upload directly.

## Two-stick / one-stick + PC demo

**Stick → PC.** Plug a USB-IR adapter into the PC, point the stick at
it, then run on the PC:

```bash
python -m opentama proximity scan --port serial:///dev/ttyUSB0 --duration 60 --rssi close
python -m opentama proximity digest               # plain-text
python -m opentama proximity digest --notify-teams   # post to Teams
```

**Stick → Stick.** Flash a second stick with a different
`OPENTAMA_PET_NAME` and add an IR receiver Hat. (Receive support in
the firmware is on the roadmap; for now use the PC path.)

## File map

```
firmware/m5stickc/
├── README.md           # ← you are here
├── platformio.ini      # PlatformIO env definition
└── src/
    ├── main.cpp        # boot, UI, HELLO loop, button handlers
    ├── opentama_proto.h
    ├── opentama_proto.cpp   # frame encoder + CRC16, byte-identical to opentama/ir/protocol.py
    ├── ir_tx.h
    └── ir_tx.cpp       # bit-bang IR LED at 9600 baud
```

## Parity with the Python implementation

The C++ encoder in `opentama_proto.cpp` is a direct port of
`opentama/ir/protocol.py:encode` and uses the same CRC-16/CCITT-FALSE
constants (poly `0x1021`, init `0xFFFF`). A round-trip test on the
Python side (`tests/test_proximity.py::test_python_decodes_c_encoded_hello`)
decodes the byte sequence the firmware produces for the default
HELLO and asserts the parsed frame matches what the C++ encoder
would output — so if you change either side, that test catches the
drift.
