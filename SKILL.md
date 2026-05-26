---
name: opentama
description: Use this skill when the user wants to interact with their OpenTama — a virtual Tamagotchi-style pet that grows only while connected to the company office WiFi, can talk to other OpenTamas over USB-attached IR adapters, can quietly log peer-pet sightings and produce a daily digest of who you ran into, can post status updates and proximity digests to a Microsoft Teams channel via a Power Automate webhook, can be extended via signed plugins, and can be rendered inside retro feature-phone (ガラケー) frames. Trigger phrases include "OpenTama", "たまごっち", "ガラケー", "check on my pet", "feed my tama", "出社", "office pet", "IR communication", "tama plugin", "Teams に通知", "Teams で報告", "post to Teams", "すれ違い", "今日のすれ違い", "proximity", "peer pet", and any mention of an office-WiFi-based virtual pet. Use this skill to hatch a new pet, check its status (optionally inside a retro phone frame), feed/play/sleep, exchange greetings/gifts/visits with another OpenTama over IR, record/list/summarise peer-pet sightings, post the pet's snapshot or the day's proximity digest to a Teams channel, or install/run a sandboxed plugin. Do NOT use for unrelated WiFi diagnostics, general productivity tools, or other virtual-pet libraries.
license: MIT
---

# OpenTama — 出社促進キット

OpenTama is a tiny Tamagotchi that lives in the developer's terminal,
grows **only** while connected to the office WiFi, can chat with other
OpenTamas via USB-attached IR adapters, and can be extended with
sandboxed plugins. Optional: render the pet inside a retro
feature-phone (ガラケー) frame for the full atmosphere.

## Quick start

```bash
# Hatch a new pet (one-time setup).
python -m opentama init たまお OfficeWiFi-SSID

# Check on it — this also advances time-based growth/decay.
python -m opentama status

# Care actions.
python -m opentama feed
python -m opentama play
python -m opentama sleep

# Render inside a retro feature-phone frame.
python -m opentama status --display monokuro   # mono early-90s
python -m opentama status --display iro        # color flip phone
python -m opentama status --display wide       # late-era widescreen
python -m opentama display list

# Talk to another OpenTama over an IR USB adapter.
python -m opentama ir greet  --port serial:///dev/ttyUSB0
python -m opentama ir gift   --port serial:///dev/ttyUSB0 --kind food
python -m opentama ir visit  --port serial:///dev/ttyUSB0
python -m opentama ir listen --port serial:///dev/ttyUSB0  # responder side

# Post the current snapshot to a Microsoft Teams channel.
export OPENTAMA_TEAMS_WEBHOOK="https://prod-XX.japaneast.logic.azure.com:443/workflows/..."
python -m opentama teams notify

# Peer-pet sightings (proximity).
python -m opentama proximity record peer-abc --nickname アリス --rssi close
python -m opentama proximity list
python -m opentama proximity digest                 # plain-text summary
python -m opentama proximity digest --notify-teams  # also post to Teams
python -m opentama proximity clear

# Listen on an IR transport and log every peer that pings us.
python -m opentama proximity scan --port serial:///dev/ttyUSB0 --duration 30
python -m opentama proximity scan --port serial:///dev/ttyUSB0 --duration 60 --rssi near

# Plugins.
python -m opentama plugin list
python -m opentama plugin checksum path/to/entry.py
python -m opentama plugin trust    ~/.opentama/plugins/stats_card
python -m opentama plugin run      stats_card
python -m opentama plugin revoke   stats_card:0.1.0

# Start over.
python -m opentama reset
```

State is persisted at `~/.opentama/state.json` (override with
`OPENTAMA_STATE_PATH`). Plugins live in `~/.opentama/plugins/`
(override with `OPENTAMA_PLUGIN_DIR`). The trust store is at
`~/.opentama/trusted_plugins.json` (override with
`OPENTAMA_TRUST_STORE`).

## When to invoke this skill

Run `python -m opentama status` proactively whenever the user:
- Mentions OpenTama / たまごっち / their office pet.
- Says something like "I just got to the office" — `status` will pick
  up the WiFi change automatically.
- Asks how their pet is doing or what stage it's at.
- Asks to see the pet "on a ガラケー" / "on a flip phone" / "in a
  retro frame" → add `--display monokuro|iro|wide`.

Run the care actions (`feed`, `play`, `sleep`) when the user explicitly
asks to perform that action, or when `status` shows the matching stat
below ~30.

For IR features:
- "Greet/visit another tama over IR" → `ir greet` / `ir visit`.
- "Send a gift to my friend's tama" → `ir gift --kind food` (or `toy`).
- "Receive an IR ping" → `ir listen`.
- The transport URI is `serial:///dev/ttyUSB0` for typical USB-IR
  adapters; `loopback://` is for local testing.

For Teams notifications:
- "Teams に通知" / "Teams で報告" / "post to Teams" → `teams notify`.
- Requires `OPENTAMA_TEAMS_WEBHOOK` to be set, or `--webhook-url` to
  be passed. The URL is the HTTP endpoint of a Power Automate
  *"When a Teams webhook request is received"* workflow.
- The payload is an Adaptive Card 1.4 wrapped in the
  `{"type": "message", "attachments": [...]}` envelope that the
  *"Post adaptive card in a chat or channel"* action expects.
- No Microsoft Graph, no OAuth — the webhook URL is the only secret.

For proximity (peer-pet sightings):
- "今日のすれ違い" / "今日 N 人とすれ違った？" / "proximity digest" →
  `proximity digest`. Add `--notify-teams` to also post the digest to
  the configured Teams channel.
- "ペットが peer-X とすれ違った" / "log a sighting" → `proximity record
  <peer-id> [--nickname X] [--lang Y] [--rssi close|near|far|unknown]`.
- "今日のすれ違い一覧" → `proximity list`.
- "すれ違いログを消して" → `proximity clear`.
- "赤外線で待ち受けて" / "IR でスキャン" / "proximity scan" →
  `proximity scan --port serial:///dev/ttyUSB0 --duration 30`. Listens
  on the IR transport for the given duration and logs every HELLO /
  GIFT / VISIT frame it sees as a sighting. The transport URI is the
  same as the `ir` subcommands (`serial://...` or `loopback://`).
- "ガラケーから赤外線で名刺を受け取って" / "IrDA vCard" / "vCard を受信" →
  `proximity scan --garake --port serial:///dev/ttyUSB0 --duration 30`.
  Same as above but parses incoming bytes as IrDA vCard / vNote
  (the vObject formats Japanese feature phones emit when you
  "赤外線で名刺を送信"), turning each vCard's `FN` (or `N` /
  `NICKNAME` fallback) into a peer id.
- Storage is a JSONL file at `~/.opentama/proximity.jsonl` (override
  with `OPENTAMA_PROXIMITY_LOG`). Records are tiny (≈100 bytes each)
  and deliberately carry only an opaque peer id, optional public
  nickname, optional language tag, signal-strength bucket, and
  timestamp — never raw social metadata.

For plugins:
- "Install/run a plugin" → walk through `plugin checksum` →
  edit `plugin.toml` → `plugin trust` → `plugin run`.
- The trust step is mandatory; loading an untrusted plugin will fail
  with a `NotTrustedError`.
- A file modified after being trusted will fail with an
  `IntegrityError` — that is by design.

If `status` reports "No OpenTama found", ask the user for a name and
their office SSID, then run `init`.

## Mechanics (for explaining things to the user)

### Core growth model

- Time-based ticks: every command updates state using the elapsed time
  since the previous tick. No background daemon needed.
- Growth points only accumulate while the current SSID matches the
  configured `company_ssid`.
- Stages by growth points: `egg → baby (10) → child (50) → teen (200)
  → adult (500) → elder (1500)`.
- Happiness decays 4× faster when away from the office than at it.
- Hunger and energy decay regardless of location; feed / sleep restore
  them.
- A stat at or below 15 marks the pet as "sick" and `status` will
  surface a `sick` event.

### IR communication

A small framed protocol over a USB-attached IR adapter:

```
+---------+---------+--------+------------------+---------+--------+
| "OT"    | version | type   | payload length   | payload | crc16  |
| 2 bytes | 1 byte  | 1 byte | 2 bytes (uint16) | N bytes | 2 bytes|
+---------+---------+--------+------------------+---------+--------+
```

CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF) over magic..payload.
Frame types: HELLO, STATE, GIFT, VISIT, ACK. Payloads are JSON for
legibility (small enough to fit comfortably in the 1 KB max payload).

High-level operations:
- `greet` — exchange names/stages, each side gets a small happiness bump.
- `gift {food|toy}` — sender's gift bumps the receiver's hunger (food)
  and happiness (food = small, toy = larger).
- `visit` — full handshake: greet → exchange → mutual happiness bonus.
  Records `met:<peer>` and `visited:<peer>` achievements on both sides.

### Plugin system (educational-grade security)

Plugins live in directories with:

```
my-plugin/
  plugin.toml    name, version, entrypoint, sha256, capabilities
  entry.py       defines a top-level `PLUGIN = MyPlugin()`
```

Capabilities (declared in the manifest, enforced at every API call):
`state.read`, `state.write`, `ir.transmit`, `ir.receive`, `display`.
Asking for a capability you didn't declare raises `CapabilityDenied`.

The trust model is "trust on first use": the user runs
`opentama plugin trust <dir>` once after checking the manifest, which
binds the plugin's `<name>:<version>` to its current SHA-256. Editing
the entry-point file invalidates the hash and refuses to load.

**What this protects against:** bit-rot, accidental edits, plugins
that try to do more than they declared.

**What it does NOT protect against:** a plugin you've explicitly
trusted that decides to `import os` and read your home directory.
True isolation would require OS-level sandboxing; this is an
educational tool, not a production runtime.

### Proximity (peer-pet sightings)

A two-tier UX for cross-pet encounters (see issue #1):

1. **Background detection.** A pluggable `Detector` quietly logs nearby
   OpenTama peers throughout the day. Concrete detectors can sit on
   top of the existing USB-IR transport, Bluetooth LE advertisements,
   mDNS on the office WiFi, or — in tests — a `LoopbackDetector`. The
   current release ships the abstract `Detector` protocol, the
   loopback, and the JSONL log; OS/hardware-specific detectors are
   left to plugins.

2. **Explicit exchange.** The owner reviews the day's sightings via
   `opentama proximity digest` and chooses which peers to actually
   transact with. The exchange itself reuses the existing `Session`
   API (`greet` / `gift` / `visit`). Nothing in this module auto-
   installs a skill or auto-gifts; humans gate every cross-pet action.

Records are intentionally tiny and metadata-light: `peer_id`,
optional `nickname`, optional `lang`, a coarse `rssi_bucket`
("close" / "near" / "far" / "unknown"), and a unix timestamp.

**IR detector.** `IRProximityDetector` wraps any
`opentama.ir.transport.IRTransport` and converts every inbound
`HELLO` / `GIFT` / `VISIT` frame into a `PeerSighting`. It is
strictly passive — it never ACKs, never returns greetings — so it
can coexist with a separate `Session.serve_once` loop that actually
performs the exchange. The `proximity scan` CLI exposes this:
listen on `serial:///dev/ttyUSB0` (or `loopback://`) for N seconds
and every peer that pings becomes a logged sighting.

`proximity digest --notify-teams` posts the summary as an Adaptive
Card via the same Power Automate webhook used by `teams notify`; the
card lists each peer once with their sighting count and the closest
signal-strength bucket observed.

### Teams integration

OpenTama posts an Adaptive Card snapshot of the pet to a Teams channel
via a Power Automate webhook. The flow expected on the other end is:

```
Trigger:  When a Teams webhook request is received
Action:   Post adaptive card in a chat or channel
          (bind the card body to the trigger payload)
```

The card includes the pet's name, current stage, an at-office / away
status line, the three core stats, day count, and the three most recent
achievement keys. No third-party Python dependencies — `opentama/teams.py`
talks to the webhook via the standard-library `urllib` only.

`OPENTAMA_TEAMS_WEBHOOK` is the URL that workflow produces. It is the
only secret involved; treat it like any other webhook URL (don't commit
it, rotate it if leaked). The CLI refuses any URL that isn't `https://`
(or `http://` for local testing) to prevent a tampered env var from
silently exfiltrating data elsewhere.

### Display backends (ガラケー)

Three retro feature-phone frames render the pet from a `StateView`
snapshot:

- `monokuro` — early-90s monochrome candybar, narrow LCD, dialpad.
- `iro` — mid-2000s color flip phone, status bar with signal/battery.
- `wide` — late-era widescreen ガラケー, mood indicator, app strip.

All use ASCII-only borders for terminal portability and a
visual-width-aware padder that handles Japanese names and emoji
correctly.

## Files

- `opentama/wifi.py` — cross-platform SSID detection (macOS, Linux,
  Windows).
- `opentama/state.py` — JSON-backed `TamaState` dataclass.
- `opentama/stages.py` — life stages and ASCII art.
- `opentama/core.py` — the `Tamagotchi` class (DI: `ssid_provider`,
  `clock`).
- `opentama/cli.py` — argparse CLI behind `python -m opentama`.
- `opentama/ir/` — protocol, transport (`SerialIRTransport`,
  `LoopbackIRTransport`), and `Session` (greet/gift/visit).
- `opentama/plugins/` — capability-based plugin API, loader, and trust
  store.
- `opentama/displays/` — three retro feature-phone display backends
  plus a visual-width-aware layout helper.
- `opentama/teams.py` — Microsoft Teams integration (Adaptive Card
  builders for both status snapshots and proximity digests, webhook
  URL resolver, HTTP POST transport, high-level `notify` /
  `notify_digest` helpers). No third-party deps.
- `opentama/proximity.py` — peer-pet sighting log, abstract `Detector`
  protocol, in-memory `LoopbackDetector`, **`IRProximityDetector`**
  (OpenTama framed-protocol → sightings), **`IrDAProximityDetector`**
  (IrDA vCard / vNote vObjects from real feature phones → sightings),
  per-peer aggregation (`summarise`), and human-readable
  `format_digest`. JSONL storage at `~/.opentama/proximity.jsonl`.
- `opentama/garake.py` — vObject (vCard / vNote / …) parser plus the
  `vobject_to_sighting` / `sightings_from_irda_blob` helpers used by
  `IrDAProximityDetector`. Handles RFC 2425 line folding, Shift-JIS
  ↔ UTF-8 best-effort decoding, and the `FN` → `N` → `NICKNAME`
  fallback ladder when mapping a vCard to a peer id.
- `firmware/m5stickc/` — PlatformIO/Arduino firmware for the M5StickC
  Plus2 that blinks OpenTama frames out the built-in IR LED. Includes
  a C++ port of the frame encoder + CRC-16/CCITT-FALSE that is held
  byte-for-byte identical to `opentama/ir/protocol.py` via
  `tests/test_firmware_parity.py`. See `firmware/m5stickc/README.md`
  for parts, pinout, and the two-stick / one-stick + PC demos.
- `examples/plugins/stats_card/` — a sample display plugin.
- `examples/plugins/ir_ping/` — a sample IR plugin (transmit + receive).

## Testing

```bash
pip install -e ".[dev]"
pytest
```

The test suite covers WiFi detection (mocked subprocess), state
persistence, growth/decay over time, the CLI, the IR wire protocol
(including CRC edge cases and resyncing on garbage), IR transports,
high-level IR sessions over a paired loopback, plugin manifest
parsing, SHA-256 integrity, trust-store semantics, capability gate
enforcement, and rendered output for each display.
