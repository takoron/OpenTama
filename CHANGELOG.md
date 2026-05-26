# Changelog

All notable changes to OpenTama are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- **`elder` sprite is now たころんの王さま (the king form).** Takoron's
  elder stage swaps the drifting steam wisps for a three-spiked
  crown sitting on top of the takoyaki body. Toppings, cheek
  dimples, and the contented smile are unchanged; the band of the
  crown spans the full ball width. Triggered by the same growth-
  points threshold as before (1500 gp). Inspired by an illustration
  the project owner sent in mid-development — see the closed PR for
  the original reference image.

### Added
- **IR-driven proximity detection.** New `IRProximityDetector` in
  `opentama/proximity.py` wraps any `opentama.ir.transport.IRTransport`
  and converts inbound `HELLO` / `GIFT` / `VISIT` frames into
  `PeerSighting` records. Strictly passive — never sends ACKs, never
  returns greetings — so it can coexist with `Session.serve_once`.
- **`python -m opentama proximity scan`** — listen on an IR transport
  for `--duration` seconds and log every peer pinging us. Uses the
  same `serial://...` / `loopback://` transport URIs as the existing
  `ir` subcommands. With this, the existing `proximity digest
  --notify-teams` pipe becomes an end-to-end office-IR ⇄ Teams flow:
  scan over IR → aggregate → post Adaptive Card to a Teams channel.
- 9 new IR-detector tests in `tests/test_proximity.py` (covering
  HELLO/GIFT/VISIT mapping, ACK rejection, buffer resync past garbage
  bytes, configurable RSSI bucket, missing-name dropping, and an
  end-to-end test that runs a real `Session.greet()` initiator on
  one loopback endpoint and confirms the other endpoint's detector
  sees the peer).
- **M5StickC ガラケー firmware (PoC).** `firmware/m5stickc/` — a
  PlatformIO/Arduino sketch that turns an M5StickC Plus2 into a
  transmit-only OpenTama pet. Every 5 seconds it blinks a `HELLO`
  frame out the built-in IR LED at 9600 baud baseband UART; button A
  sends `GIFT`, button B sends `VISIT`. LCD draws a ガラケー-style
  screen with the pet name + stage + "carrier strip" header. The
  frame encoder (`opentama_proto.cpp`) is a byte-for-byte port of
  `opentama/ir/protocol.py:encode`, including the CRC-16/CCITT-FALSE
  parameters. Pair it with `python -m opentama proximity scan
  --port serial:///dev/ttyUSB0` on a PC with a USB-IR adapter to
  complete the IR → proximity log → Teams pipeline.
- **Firmware parity test.** `tests/test_firmware_parity.py` (4 cases)
  pins the exact on-the-wire bytes the firmware should produce for
  its default HELLO, cross-checks the structural invariants the C++
  encoder hard-codes (magic / version / BE payload length / CRC),
  Python round-trip-decodes the locked byte sequence, and includes a
  CRC-16/CCITT-FALSE known-vector check
  (`crc16(b"123456789") == 0x29B1`). Any drift in either Python or
  C++ encoders trips this immediately.

## [0.4.0] — 2026-05-26

### Added
- **Microsoft Teams integration.** `python -m opentama teams notify`
  posts an Adaptive Card 1.4 snapshot of the pet (name, stage, stats,
  recent achievements, office/away state) to a Microsoft Teams channel
  via a Power Automate *"When a Teams webhook request is received"*
  workflow. Webhook URL comes from `OPENTAMA_TEAMS_WEBHOOK` or
  `--webhook-url`. No Microsoft Graph, no OAuth — the URL is the only
  secret. The CLI refuses non-HTTP(S) URLs to prevent env-var tampering
  from silently exfiltrating data.
- **Proximity (peer-pet sightings).** Two-tier UX for cross-pet
  encounters (see issue #1): a background detection layer logs nearby
  OpenTama peers as tiny JSONL records (≈100 bytes each, opaque peer
  id + optional nickname/lang + rssi bucket + timestamp), and an
  explicit `proximity digest` step lets the owner review the day's
  encounters before any actual exchange. New CLI subcommands:
  `proximity {record, list, digest, clear}`. `proximity digest
  --notify-teams` posts the summary as an Adaptive Card via the same
  Power Automate webhook used by `teams notify`. Storage path:
  `~/.opentama/proximity.jsonl` (override with
  `OPENTAMA_PROXIMITY_LOG`).
- `opentama/teams.py` — `build_status_card`, `build_digest_card`,
  `resolve_webhook_url`, `post_card`, `notify`, `notify_digest`,
  typed errors `TeamsConfigError`, `TeamsTransportError`. No
  third-party Python dependencies; uses `urllib` only.
- `opentama/proximity.py` — `PeerSighting`, append-only JSONL log,
  abstract `Detector` protocol, in-memory `LoopbackDetector`, per-peer
  aggregation (`summarise`), human-readable `format_digest`. The
  current release ships the abstract `Detector` and the loopback;
  OS/hardware-specific detectors (USB-IR, BLE, mDNS) are left to
  plugins.
- `tests/test_teams.py` — 29 tests covering payload shape (status +
  digest cards), office vs. away framing, sick marking, achievement
  truncation, UTF-8 round-tripping, env-var resolution, URL
  validation, HTTP and URL error wrapping, response cleanup, and the
  high-level `notify` / `notify_digest` helpers.
- `tests/test_proximity.py` — 19 tests covering sighting
  immutability, log path resolution, append/load round-trip, since
  filter, corrupt-line handling, loopback detector draining,
  per-peer aggregation, RSSI bucket priority, window filters, and
  digest formatting.
- `HARDWARE.md` — design note for a possible M5StickC + IR hardware
  edition (future work, not implemented).

### Fixed
- **Windows + Japanese-locale crash in `wifi.get_current_ssid`.**
  `netsh wlan show interfaces` on Japanese Windows occasionally emits
  bytes the OS-default decoder rejects (e.g. `0x86`), which crashed
  the subprocess reader thread and left `r.stdout = None`, surfacing
  as an `AttributeError` from any CLI command that calls `tick()`
  (`status`, `feed`, `play`, `sleep`). Now decodes with
  `errors="replace"` and defensively checks `r.stdout is None`. Full
  suite passes 200/200 on JA-locale Windows hosts.

## [0.3.4] — 2026-05-15

### Added
- **`NOTICE`** file at the repo root summarising the split between
  MIT-licensed software and `CHARACTER.md`-governed Takoron art.
- Formal permission text in `CHARACTER.md` covering internal use,
  public redistribution of this repo unchanged, and the scope of what
  the bundled sprites do *not* license (the LINE sticker artwork
  itself, derivative character art, merchandising).

### Changed
- README has an explicit "code MIT, character per CHARACTER.md"
  section so the dual-licensing is visible up front.
- `CHARACTER.md` now links to the original LINE sticker set
  (*タコロンばかり２*) as the canonical reference for the character.

## [0.3.3] — 2026-05-15

### Added
- **`CHARACTER.md`** crediting the original Takoron character to its
  creator (the LINE sticker artist). Includes a short guide on
  swapping in your own pet by replacing `opentama/sprites.py`.

### Changed
- Refined every sprite from the artist's reference: cheek dimples
  appear in `baby` onward, the bonito flake is more prominent,
  `adult` now has an explicit tongue pixel in the open mouth, and
  `elder` has clearer drifting steam wisps.
- README updated with a link to `CHARACTER.md` and refreshed screenshot.

## [0.3.2] — 2026-05-15

### Changed
- **Takoron is a takoyaki, not an octopus.** Redesigned every sprite
  after a reference drawing of the actual mascot. The pet is a round
  takoyaki ball with:
  - A bonito flake (かつおぶし) standing up at the top right.
  - Sauce / nori / pickled-ginger topping dots scattered on the upper
    half.
  - A `^_^` closed-eye smile (two rows of half-block crescents).
  - An open mouth with the tongue peeking out (adult stage).
  - Steam wisps drifting up (elder stage).
- Stage progression now tells the story: plain dough → face appears →
  first topping → flake rises → full takoyaki → wise elder with steam.

## [0.3.1] — 2026-05-15

### Changed
- **Takoron (たころん) redesign.** The pet is now an octopus mascot
  named Takoron, with proper symmetric eye placement, dimpled cheeks,
  smile, and tentacles. Sprite grids enlarged to 14×16 (rendered as
  14 cells × 8 lines) so there is room for facial detail. The
  `sick` overlay now puts sweat drops at the corners.
- Tightened `iro` name line format so 4-character Japanese names
  (e.g. たころん) fit inside the LCD without truncation.

## [0.3.0] — 2026-05-15

### Added
- **Pixel-art sprites.** The pet is now drawn as a 12×12 monochrome
  bitmap rendered with Unicode half-block characters (`▀ ▄ █`) — small
  enough that it could plausibly run on a real ガラケー LCD. Six
  hand-designed sprites (egg → elder) plus a "sick" overlay.
- `opentama.sprites` module + `test_sprites.py` (14 new tests).
- `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`, GitHub Actions CI
  workflow, issue / PR templates — first cut at being a proper OSS
  project for internal-company distribution.

### Changed
- `Stage.art` is now a property that delegates to the sprite renderer.
- All three display backends (`monokuro`, `iro`, `wide`) render the new
  pixel pet inside the LCD area. Compact name/stage formatting so
  Japanese names fit within the screen budget.

### Removed
- Per-stage `EGG_ART` / `BABY_ART` / … module-level constants in
  `stages.py`. `Stage.art` is the only entry point now.

## [0.2.0] — 2026-05-15

### Added
- **USB-IR communication.** Framed protocol (`magic | version | type |
  length | payload | crc16`), USB serial transport plus an in-memory
  loopback for tests, and high-level `Session` operations:
  `greet` / `gift` / `visit` / `listen`.
- **Plugin system.** Capability-based API (`state.read`, `state.write`,
  `ir.transmit`, `ir.receive`, `display`), SHA-256 integrity, and a
  trust-on-first-use store. `opentama plugin {list,trust,revoke,run,checksum}`.
- **Three retro feature-phone display backends** (ガラケー):
  `monokuro` (early-90s monochrome), `iro` (mid-2000s color flip),
  `wide` (late-era widescreen). Visual-width-aware padding so Japanese
  names and emoji don't break alignment.
- Sample plugins in `examples/plugins/` (`stats_card`, `ir_ping`).
- 76 new tests covering IR, plugins, and displays.

## [0.1.0] — 2026-05-15

### Added
- Initial release. WiFi-gated growth/decay engine, six life stages,
  state persistence at `~/.opentama/state.json`, care actions (feed,
  play, sleep), CLI behind `python -m opentama`, 62 tests.
