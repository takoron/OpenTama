# Changelog

All notable changes to OpenTama are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Microsoft Teams integration.** `python -m opentama teams notify`
  posts an Adaptive Card 1.4 snapshot of the pet (name, stage, stats,
  recent achievements, office/away state) to a Microsoft Teams channel
  via a Power Automate *"When a Teams webhook request is received"*
  workflow. Webhook URL comes from `OPENTAMA_TEAMS_WEBHOOK` or
  `--webhook-url`. No Microsoft Graph, no OAuth — the URL is the only
  secret. The CLI refuses non-HTTP(S) URLs to prevent env-var tampering
  from silently exfiltrating data.
- `opentama/teams.py` — `build_status_card` / `resolve_webhook_url` /
  `post_card` / `notify` plus typed errors `TeamsConfigError`,
  `TeamsTransportError`. No third-party Python dependencies; uses
  `urllib` only.
- `tests/test_teams.py` — 22 new tests covering payload shape,
  office vs. away framing, sick marking, achievement truncation,
  UTF-8 round-tripping, env-var resolution, URL validation, HTTP
  and URL error wrapping, response cleanup, and the high-level
  `notify` helper.
- `HARDWARE.md` — design note for a possible M5StickC + IR hardware
  edition (future work, not implemented).

### Fixed
- **Windows + Japanese-locale crash in `wifi.get_current_ssid`.**
  `netsh wlan show interfaces` on Japanese Windows occasionally emits
  bytes the OS-default decoder rejects (e.g. `0x86`), which crashed
  the subprocess reader thread and left `r.stdout = None`, surfacing
  as an `AttributeError` from any CLI command that calls `tick()`
  (`status`, `feed`, `play`, `sleep`). Now decodes with
  `errors="replace"` and defensively checks `r.stdout is None`. Fixes
  three previously-failing `tests/test_cli.py` cases on JA-locale
  Windows hosts; suite now passes 174/174 there.

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
