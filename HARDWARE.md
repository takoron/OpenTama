# OpenTama Hardware Concept — M5StickC Edition

> **Status:** Draft / brainstorm. Nothing implemented yet. This is a
> design note for a possible v0.5+ direction, not a commitment.

OpenTama already speaks an IR-style framed protocol over USB serial
(see v0.2.0 in [CHANGELOG.md](CHANGELOG.md): `magic | version | type |
length | payload | crc16`, with `Session` operations `greet` / `gift`
/ `visit` / `listen`). This document sketches what it would look like
to lift that same protocol off of USB and onto **real infrared**, using
a tiny battery-powered device that the user can carry around the
office.

## Why hardware at all?

The current OpenTama experience runs entirely inside Claude Code on the
user's PC, gated by office WiFi. That is a great fit for "the pet
lives at your desk." It is a poor fit for the **赤外線たまごっち** mental
model the project is reaching for — the part where you turn to a
colleague at lunch, point your device, and your pets meet.

A dedicated palm-sized companion device gives us:

- **Physical presence.** The pet lives somewhere other than a terminal
  window. You can put it on your desk, in your pocket, on a lanyard.
- **Literal infrared.** "Aim and click" is the original UX. Doing it
  with real IR (not BLE, not WiFi, not mDNS) preserves the metaphor.
- **Network hygiene.** No new traffic on the corporate WiFi.
  Cross-pet exchange happens in free space, point-to-point, with no
  server in between.
- **Cost.** ~¥3,000 per unit means a team can equip itself out of
  someone's snack budget.

## Target device: M5StickC Plus2

| Feature | What it gives us |
|---|---|
| ESP32-PICO-V3-02 | Plenty of headroom for the framed IR protocol + a tiny state machine. Has WiFi + BLE built in if we ever want them. |
| **IR LED (transmit)** | The actual point. Drive it with the same byte stream we already use over USB. |
| 1.14" 135×240 color LCD | Enough pixels to render Takoron sprites at a comfortable size; small enough to feel like a keychain pet. |
| 2 buttons + 6-axis IMU | Feed / play / sleep + "shake to wake." |
| 200 mAh battery, USB-C | A workday on a charge is plausible if we sleep aggressively. |
| ~¥3,000 | Affordable for internal distribution. |

The "Plus2" variant is preferred over the original Stick C because of
the larger LCD and the second button — both matter once you try to
play a care game on it.

## Architecture sketch

```
   ┌────────────────────────┐               ┌────────────────────────┐
   │ Owner A's PC           │               │ Owner B's PC           │
   │ ┌────────────────────┐ │               │ ┌────────────────────┐ │
   │ │ Claude Code        │ │               │ │ Claude Code        │ │
   │ │  + OpenTama skill  │ │               │ │  + OpenTama skill  │ │
   │ └─────────┬──────────┘ │               │ └─────────┬──────────┘ │
   │           │ BLE / USB  │               │           │ BLE / USB  │
   └───────────┼────────────┘               └───────────┼────────────┘
               │                                        │
       ┌───────▼───────┐                       ┌────────▼──────┐
       │ M5StickC A    │   ◀── IR (line of    │ M5StickC B    │
       │ (Takoron #001)│         sight) ──▶    │ (Takoron #002)│
       └───────────────┘                       └───────────────┘
```

Two transports, one protocol:

1. **PC ⇄ M5StickC** — BLE (preferred, no cable) or USB serial
   fallback. Carries the same framed messages the project already
   defines, just over a different physical link.
2. **M5StickC ⇄ M5StickC** — IR LED + IR receiver, line of sight,
   ≤1 m, ≤2 kbps. Same framed messages, fragmented if needed.

Crucially, neither path adds a new protocol surface. The reusable
piece is the work already done in v0.2.0.

## What gets exchanged over IR

Mirroring the existing `Session` API, with payload sizes that respect
IR's slow, lossy, half-duplex reality:

| Phase | Message type | Payload | Notes |
|---|---|---|---|
| 1 | `greet` | pet id + nickname + stage (~16 bytes) | Just "hi, I exist." |
| 2 | `gift` | care item id + amount (~8 bytes) | Existing op, retargeted. |
| 3 | `visit` | pet stats snapshot (~64 bytes) | Owner-controlled granularity. |
| 4 | skill metadata | skill name + SHA-256 + 1-line summary (~96 bytes) | Metadata only — the actual skill content syncs later from a trusted source if the owner approves. |

The skill-exchange step deliberately does **not** carry the skill
itself over IR. IR ships only a fingerprint; the owner sees "your
peer offers `slack-summarizer`, sha256 abc…" and chooses whether to
fetch the real file from the shared internal source.

## Why IR and not BLE/Wi-Fi for peer exchange

BLE advertisements are tempting — they'd auto-detect every peer
within ~10 m. But that exact property is the problem:

- **Ambient discovery is creepy.** "Your pet noticed everyone in this
  meeting room" is not a feature people want. Discovery without
  intent leaks social information.
- **Range is wrong.** We want "the colleague I'm actually talking
  to," not "everyone on this floor."
- **Governance.** IT teams understand "device with no network stack
  that beams at another device" far better than they understand "BLE
  mesh with a custom GATT service."

IR forces the user to physically aim. That single gesture is the
consent layer.

(BLE may still earn a role as the **PC ⇄ stick** transport, where
it's a wire replacement, not a discovery channel.)

## Non-goals

- **Running Claude on the stick.** ESP32 isn't going to run an LLM,
  and that's fine. The stick is a peripheral; cognition stays on the
  PC.
- **Internet-side traffic.** Pet ⇄ pet must work without any cloud
  call. The PC may sync with internal sources, but the IR exchange
  itself is offline.
- **Auto-installing skills.** Receiving a skill fingerprint never
  installs anything. The owner approves every skill, every time.

## Open questions

- **Pairing model:** does each stick belong to one PC, or can a PC
  see multiple sticks (family of pets)?
- **Identity:** is the pet id stable across firmware reflash? Should
  it be a hash of the owner's GitHub identity, a random UUID, or a
  human-chosen string?
- **Battery life target:** is "a workday with a 30-minute lunch
  meet" enough, or do we need multi-day standby?
- **Sprite asset format on-device:** do we ship the Takoron sprites
  as PNGs in flash, or render them from the same `opentama.sprites`
  primitives the PC uses, ported to C?
- **Fragmentation over IR:** the existing protocol assumes a stream;
  IR will need a max-frame and a retry policy. What's the right
  default for a noisy office environment?

## Suggested first proof of concept

1. Buy **two** M5StickC Plus2 units.
2. Port the framed protocol from `opentama/ir.py` (the v0.2.0 work)
   to Arduino/PlatformIO C, reusing the same magic bytes and CRC16.
3. Get `greet` working end-to-end: PC A → stick A → IR → stick B →
   PC B, with both PCs showing "your pet met Takoron #002 at
   2026-MM-DD HH:MM."
4. Decide whether to keep going based on whether step 3 felt like a
   real meeting or a debug session.

If step 3 lands, the rest is incremental: `gift`, `visit`, then the
skill-fingerprint exchange.

## Related

- [CHANGELOG.md](CHANGELOG.md) — see v0.2.0 for the existing USB-IR
  protocol this design extends.
- `opentama/ir.py` — the framed protocol implementation that would be
  ported to firmware.
- `examples/plugins/ir_ping/` — the simplest existing plugin that
  exercises the IR transport; a good template for the M5StickC
  loopback test.
