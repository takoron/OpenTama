# OpenTama 🥚

> 出社促進キット — a Tamagotchi-style virtual pet that grows **only** while you're connected to the office WiFi. Optional retro ガラケー display, IR communication with other pets, and a sandboxed plugin system for hacking on it.

Built as a Claude Code skill: drop the directory into the place where your client looks for skills, and Claude will know to use it whenever you mention OpenTama, your office pet, your たまごっち, or 出社.

## Why

- Your pet **grows** while you're at the office (configured WiFi SSID).
- It **decays** while you're away — happiness 4× faster than at the office.
- All time-based. No background daemon. Every command advances state.
- Built to be **understood**: small modules, dependency-injected core, ~140 tests.
- Built to be **hacked on**: plugin API with explicit capabilities, signed integrity, a trust store.
- Built to be **enjoyed**: render your pet on a monochrome 90s candybar, a color flip phone, or a late-era widescreen ガラケー.

## Install

```bash
pip install -e .
```

Python 3.11+ (uses stdlib `tomllib`). For IR over real hardware, also `pip install pyserial`.

## CLI cheat sheet

### Core

```bash
python -m opentama init たまお OfficeWiFi-SSID
python -m opentama status                   # default text status
python -m opentama status --display monokuro|iro|wide   # render in a ガラケー frame
python -m opentama feed
python -m opentama play
python -m opentama sleep
python -m opentama reset
```

### IR communication (between two OpenTamas)

```bash
# initiator side
python -m opentama ir greet  --port serial:///dev/ttyUSB0
python -m opentama ir gift   --port serial:///dev/ttyUSB0 --kind food   # or --kind toy
python -m opentama ir visit  --port serial:///dev/ttyUSB0

# responder side (the friend's machine)
python -m opentama ir listen --port serial:///dev/ttyUSB0
```

`--port loopback://` is also accepted for local round-tripping; useful for plugin testing.

### Plugins

```bash
python -m opentama plugin list                              # show discovered plugins
python -m opentama plugin checksum entry.py                 # SHA-256 to paste into plugin.toml
python -m opentama plugin trust  ~/.opentama/plugins/foo    # pin <name>:<version> → <sha256>
python -m opentama plugin revoke foo:0.1.0
python -m opentama plugin run    foo                        # load + verify + run
python -m opentama plugin run    foo --port serial:///dev/ttyUSB0   # for IR plugins
```

## Building a plugin

A plugin is a directory with two files. See `examples/plugins/` for working samples.

```
my-plugin/
  plugin.toml    # manifest
  entry.py       # defines a top-level `PLUGIN = MyPlugin()`
```

`entry.py`:

```python
from opentama.plugins import DisplayPlugin

class MyDisplay(DisplayPlugin):
    name = "my-display"
    version = "0.1.0"

    def render(self, view):
        return f"hello {view.name}!"

PLUGIN = MyDisplay()
```

`plugin.toml`:

```toml
name = "my-display"
version = "0.1.0"
entrypoint = "entry"
plugin_object = "PLUGIN"
sha256 = "<paste output of `opentama plugin checksum entry.py`>"
capabilities = ["state.read", "display"]
```

Available capabilities, enforced at every API call on the
`PluginContext` you receive:

| capability     | what it lets you do                                    |
|----------------|--------------------------------------------------------|
| `state.read`   | `ctx.get_state()` — a read-only snapshot               |
| `state.write`  | `ctx.feed()`, `ctx.play()` (or extend in your fork)   |
| `ir.transmit`  | `ctx.ir_send(bytes)`                                   |
| `ir.receive`   | `ctx.ir_recv(timeout=…)`                               |
| `display`      | run via `opentama plugin run` and have output printed |

Using a capability you didn't declare raises `CapabilityDenied`.

### Trust model

Plugins are loaded only if both checks pass:

1. **Integrity**: the entry-point file's SHA-256 matches `sha256` in
   the manifest. Edit the file, and load fails.
2. **Trust**: an entry exists in `~/.opentama/trusted_plugins.json`
   binding `<name>:<version>` to the matching `<sha256>`. You add this
   with `opentama plugin trust <dir>`.

This is **educational-grade** security — it stops accidents and
capability creep, not a determined attacker writing `import os` after
you've trusted them. Real isolation would need OS-level sandboxing
(subprocesses, seccomp, wasm).

### Files

```
opentama/
├── core.py            # the Tamagotchi class (DI: ssid_provider, clock)
├── state.py           # JSON-backed TamaState
├── stages.py          # life stages + ASCII art
├── wifi.py            # cross-platform SSID detection
├── cli.py             # argparse CLI behind `python -m opentama`
├── ir/
│   ├── protocol.py    # frames + CRC16-CCITT-FALSE + parse_stream
│   ├── transport.py   # SerialIRTransport, LoopbackIRTransport
│   └── session.py     # greet / gift / visit
├── plugins/
│   ├── api.py         # Capability, PluginContext, Plugin base classes
│   └── loader.py      # PluginManifest, integrity, TrustStore, PluginLoader
└── displays/
    ├── _layout.py     # visual-width-aware padding
    ├── monokuro.py    # mono early-90s candybar
    ├── iro.py         # color mid-2000s flip
    └── wide.py        # late-era widescreen ガラケー
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

The suite hits each layer:

- WiFi detection across macOS/Linux/Windows (mocked subprocess).
- State persistence (atomic writes, forward-compatible loads).
- Growth + decay over time, stage transitions, milestones, sickness.
- CLI commands.
- IR wire protocol: CRC vectors, round-trips with Japanese payloads,
  every error class (bad magic / version / CRC / length / unknown
  type), stream parsing with garbage prefix and partial-tail.
- IR transports: paired loopback, timeouts, threading, plus a fake
  serial driving `SerialIRTransport`.
- IR sessions: greet, gift food, gift toy, visit — all over a paired
  loopback with both sides driven concurrently.
- Plugins: manifest parsing, integrity (positive + tamper), trust
  store (save, load, revoke, version-specific, sha-specific),
  loader (discover, refuse-untrusted, allow-untrusted, name-mismatch).
- Capability gating: every capability has an allow-and-deny test;
  `make_context` is verified to refuse to wire IR for display-only
  plugins.
- Displays: rendering for every stage, visual-width sanity, distinct
  outputs for each backend, mood reflection.

## License

MIT.
