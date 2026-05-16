# OpenTama 🥚

> **出社促進キット.** A Tamagotchi-style virtual pet that grows **only**
> while you're connected to the office WiFi. Ships as a Claude Code
> skill, talks to other OpenTamas over USB IR, and lives inside a retro
> ガラケー frame.

| | |
|--|--|
| status | beta — 152 tests, three OS targets in CI |
| python | 3.11 + (uses stdlib `tomllib`) |
| license | MIT |
| size | < 30 KB of source; zero runtime dependencies (pyserial optional for IR hardware) |

---

## What it is

OpenTama is a small terminal pet — a takoyaki mascot named **Takoron
(たころん)**, complete with bonito flake on top — that:

- **Grows** while your WiFi SSID matches the configured office SSID.
- **Decays** when you're away — happiness 4× faster than at the office.
- **Renders as a pixel sprite** inside one of three retro feature-phone
  frames (monochrome 90s candybar / mid-2000s color flip / late-era
  widescreen ガラケー). Drawn with Unicode half-blocks (`▀ ▄ █`) so it
  could plausibly run on a real ガラケー LCD.
- **Talks to other OpenTamas** over a USB-attached IR adapter using a
  small framed protocol with CRC16-CCITT.
- **Is extensible** via a sandboxed plugin system: capabilities, SHA-256
  integrity, and a trust-on-first-use store.

It's also a [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
skill — drop the folder into `~/.claude/skills/` and Claude will use the
pet whenever you mention OpenTama, your office pet, your たまごっち, or
出社. See [INSTALL.md](INSTALL.md) for the full Claude Code wiring guide.

## Install

For yourself:

```bash
pip install opentama                  # once published to your index
# or, from a checkout
pip install -e ".[dev]"
```

For internal company distribution, the typical setup is:

```bash
# 1) Maintainer publishes to the company package index.
python -m build && twine upload --repository internal dist/*

# 2) Everyone else installs from there.
pipx install --index-url https://pypi.internal.example.com/simple opentama
```

For IR hardware support:

```bash
pip install "opentama[ir]"            # adds pyserial
```

## Quick start

```bash
# Hatch (one-time).
opentama init たまお YourOfficeSSID

# See the pet inside a retro frame.
opentama status --display iro

# Care.
opentama feed
opentama play
opentama sleep

# Talk to a teammate's pet over a USB IR adapter.
opentama ir greet --port serial:///dev/ttyUSB0
```

`opentama --help` lists everything. Detailed CLI docs:
[docs/CLI.md](docs/CLI.md) (if present in your fork — same content as in
[SKILL.md](SKILL.md)).

## What it looks like

```
  +----------------------------+
  | .                       () |
  +----------------------------+
  | :D たころん adult 520gp    |
  |                            |
  |               ▄██▄         |
  |            ▄▄██▄██▄        |
  |         ▄▄██▀███▀███       |
  |         ████████▄███       |
  |         ███▀████▀███       |
  |         ██▄▄████▄▄██       |
  |         ████▄▄ ▄████▄      |
  |          ▀████████▀        |
  |                            |
  | happy   #########...  80   |
  | hungry  #########...  80   |
  | energy  #########...  80   |
  +----------------------------+
  |  feed  play  sleep  ir  cfg|
  +----------------------------+
  |  [ < ]  [ OK ]   [ > ]     |
  +----------------------------+
```

Bonito flake on top, sauce + nori + ginger dots on the upper half,
`^_^` closed eyes, open smile with a tongue peeking out.

## Sharing the pet inside your company

There are three good ways:

1. **As a Python package on your internal index.** Anyone runs
   `pipx install opentama` and they're done. Each colleague has their
   own pet but the binary is centrally maintained.

2. **As a Claude Code skill in a project repo.** Drop OpenTama into
   `.claude/skills/opentama/` inside a shared project, commit it, and
   every contributor's Claude Code session will use the pet
   automatically. See [INSTALL.md](INSTALL.md).

3. **As a personal dotfile.** Symlink your clone to
   `~/.claude/skills/opentama/`. Each person manages their own checkout.

Pets stay personal because state lives in `~/.opentama/state.json`,
which is *not* in the repo (see `.gitignore`).

## Files

```
opentama/
├── core.py            # the Tamagotchi class (DI: ssid_provider, clock)
├── state.py           # JSON-backed TamaState
├── stages.py          # life stages
├── sprites.py         # pixel-art bitmaps + half-block renderer
├── wifi.py            # cross-platform SSID detection
├── cli.py             # argparse CLI (opentama / python -m opentama)
├── ir/
│   ├── protocol.py    # frames + CRC16-CCITT-FALSE + parse_stream
│   ├── transport.py   # SerialIRTransport, LoopbackIRTransport
│   └── session.py     # greet / gift / visit
├── plugins/
│   ├── api.py         # Capability, PluginContext, Plugin base classes
│   └── loader.py      # manifest, integrity, TrustStore, PluginLoader
└── displays/
    ├── _layout.py     # visual-width-aware padding
    ├── monokuro.py    # mono early-90s candybar
    ├── iro.py         # color mid-2000s flip
    └── wide.py        # late-era widescreen ガラケー
```

Plus `examples/plugins/` with two reference plugins (`stats_card`,
`ir_ping`) and `tests/` with 152 tests.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

The suite covers WiFi detection (mocked subprocess), state persistence,
growth/decay over time, the CLI, the IR wire protocol (CRC vectors,
round-trips with Japanese payloads, every error class, resync on
garbage), IR transports (loopback + fake serial), high-level IR
sessions (concurrent loopback), plugin manifest parsing, SHA-256
integrity (positive + tamper), trust store semantics, capability
gating, the pixel sprite renderer, and rendered output for each
display.

CI runs on Ubuntu / macOS / Windows × Python 3.11 / 3.12 / 3.13.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). TL;DR: keep it small, keep it
honest, add a test.

## License

MIT. See [LICENSE](LICENSE).
