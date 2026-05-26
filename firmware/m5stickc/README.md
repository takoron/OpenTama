# OpenTama M5StickC firmware — "ガラケー赤外線たまごっち"

A tiny ESP32 firmware that turns an [M5StickC Plus2](https://docs.m5stack.com/en/core/M5StickC%20PLUS2)
into a physical OpenTama pet that periodically introduces itself over
its built-in IR LED **and** — with an external IR Receiver Unit
plugged into the Grove port — listens for peers' transmissions and
shows the most recently sighted name right on its own LCD. Pair two
of them and you have a literal stick-to-stick 赤外線たまごっち sitting
on your desk; pair one with a PC running
`python -m opentama proximity scan` for the office-IR ⇄ Teams pipeline.

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

## Receive (NEW)

The Plus2's built-in chip is an IR **LED** only — no photodiode — so
true bidirectional behaviour needs an external receiver. Plug an
[M5Stack IR Unit](https://docs.m5stack.com/en/unit/ir) (or any
TFDU-class IR-UART receiver) into the Grove port and the firmware
will:

- Listen on **GPIO 33** at 9600 baud baseband UART (configurable via
  `OPENTAMA_IR_RX_PIN` in `platformio.ini`; set to `-1` for a
  transmit-only build).
- Parse every incoming OpenTama frame using `tryParseFrame()` in
  `src/opentama_proto.cpp` — same MAGIC resync / CRC-16/CCITT-FALSE
  check / version gate as `opentama.ir.protocol.parse_stream` on the
  Python side.
- For HELLO / STATE / GIFT / VISIT, extract the peer name (`name` /
  `from`) and:
  - print it to USB serial (`RX HELLO from <name> (NN B payload)`),
  - flash a yellow "RX" badge on the LCD,
  - update the persistent "RX: \<name\> (#N)" strip at the bottom of
    the screen, where N is the lifetime sighting count.
- ACK frames are logged but don't update the peer display (they carry
  no useful identifier on their own).

The receive buffer is bounded at 1 KB and self-trims if a noisy line
overflows it, so a misaimed neighbouring stick can't wedge the loop.

## What it does *not* do (yet)

- **No state sync from PC.** Pet name / stage / gp are compile-time
  constants set by `OPENTAMA_PET_NAME` / `OPENTAMA_PET_STAGE` /
  `OPENTAMA_PET_GP` in `platformio.ini`. Re-flash to change them.
- **No power management.** It just hellos every 5 seconds forever.
  Workable on USB-C power; the 200 mAh battery will not last a day
  with the current duty cycle.
- **No bidirectional handshake.** RX is observational only — the
  stick logs peers, it doesn't return HELLO automatically or apply
  happiness deltas. That's the same passive design `IRProximityDetector`
  uses on the PC side, and it keeps the firmware tiny.

These are all explicit follow-up scope, not bugs.

## Parts

| What | Why | Approx. cost |
|---|---|---|
| M5StickC Plus2 (or original M5StickC) | The brain + LCD + IR LED + 2 buttons. | ¥3,000 |
| USB-C cable | Power + flashing. | already have it |
| (optional) USB-IR adapter on the receiving PC | Lets a PC pick up the stick's transmissions and feed them into `proximity scan`. Look for "SIR" / "9600 baud" / "TFDU"-class adapters. | ¥1,500–¥3,000 |
| (optional) [M5Stack IR Unit](https://docs.m5stack.com/en/unit/ir) on the Grove port | Enables **receive** — lets the stick observe nearby peers and surface them on its LCD. | ¥800 |

## Pinout

| Direction | Default pin | Notes |
|---|---|---|
| **IR TX** (LED) | GPIO 19 (Plus2) / GPIO 9 (original Stick C) | Override at build time via `-DOPENTAMA_IR_LED_PIN=N`. |
| **IR RX** (receiver data line) | GPIO 33 — Plus2 Grove port | Override via `-DOPENTAMA_IR_RX_PIN=N`. Set to `-1` to compile a transmit-only firmware. |

Grove wiring is direct: red → 3.3 V, black → GND, white (data) → GPIO 33.

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

**Stick → Stick.** Flash each stick with a different `OPENTAMA_PET_NAME`,
plug an M5Stack IR Unit into the Grove port of the listener, and aim
the transmitter's LED at the receiver's Unit window. The receiver's
LCD shows `RX: <peer name> (#N)` at the bottom of the screen and the
USB serial log prints `RX HELLO from <peer> ...`. Swap roles to confirm
the symmetric case.

## File map

```
firmware/m5stickc/
├── README.md           # ← you are here
├── platformio.ini      # PlatformIO env definition
└── src/
    ├── main.cpp        # boot, UI, HELLO loop, button handlers, RX loop
    ├── opentama_proto.h
    ├── opentama_proto.cpp   # frame encoder + decoder + CRC16, byte-identical to opentama/ir/protocol.py
    ├── ir_tx.h
    ├── ir_tx.cpp       # bit-bang IR LED at 9600 baud
    ├── ir_rx.h
    └── ir_rx.cpp       # Serial1-backed IR receiver
```

## Parity with the Python implementation

Both halves of `opentama_proto.cpp` mirror their Python counterparts:

| C++ function | Python counterpart | Test |
|---|---|---|
| `encodeFrame()` | `opentama.ir.protocol.encode()` | `tests/test_firmware_parity.py::test_hello_bytes_locked` (byte-for-byte hex lock) |
| `tryParseFrame()` | `opentama.ir.protocol.decode()` + `parse_stream()` | `tests/test_firmware_parity.py::test_python_round_trip_of_firmware_bytes` |
| `crc16()` | `opentama.ir.protocol.crc16()` | `tests/test_firmware_parity.py::test_crc16_known_vector` (`crc16(b"123456789") == 0x29B1`) |

`tryParseFrame()` implements the same MAGIC resync rule as Python's
`parse_stream` — non-zero `*consumed` on parse failure means "skip
past the garbage / bad-CRC / wrong-version magic and try again";
zero means "need more bytes, keep what you have."
