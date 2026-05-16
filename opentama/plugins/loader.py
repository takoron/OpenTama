"""Plugin discovery, verification, and loading.

A plugin directory looks like:

    my-plugin/
      plugin.toml
      entry.py

``plugin.toml`` (using stdlib ``tomllib`` to avoid a runtime dep)::

    name = "my-plugin"
    version = "0.1.0"
    entrypoint = "entry"        # module file (without .py)
    plugin_object = "PLUGIN"    # attribute holding the Plugin instance
    capabilities = ["display"]
    sha256 = "<hex digest of entry.py>"

The trust store is a JSON file at ``~/.opentama/trusted_plugins.json``
(overridable via ``OPENTAMA_TRUST_STORE``) mapping
``"<plugin_name>:<version>"`` → ``"<sha256>"``. A plugin can only load
if its declared SHA-256 matches the actual entry-point file *and* an
entry exists in the trust store binding that name@version to that
hash. The CLI offers a ``plugin trust`` action to record this.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib  # type: ignore

from .api import Capability, Plugin, PluginContext


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PluginError(Exception):
    """Base for plugin loading errors."""


class ManifestError(PluginError):
    pass


class IntegrityError(PluginError):
    pass


class NotTrustedError(PluginError):
    pass


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PluginManifest:
    name: str
    version: str
    entrypoint: str
    plugin_object: str
    capabilities: tuple[Capability, ...]
    sha256: str
    source_dir: Path

    @property
    def entry_path(self) -> Path:
        return self.source_dir / f"{self.entrypoint}.py"

    @property
    def trust_key(self) -> str:
        return f"{self.name}:{self.version}"


def parse_manifest(plugin_dir: Path) -> PluginManifest:
    mpath = plugin_dir / "plugin.toml"
    if not mpath.exists():
        raise ManifestError(f"missing plugin.toml in {plugin_dir}")
    with mpath.open("rb") as f:
        data = tomllib.load(f)

    required = ("name", "version", "entrypoint", "sha256")
    for key in required:
        if key not in data:
            raise ManifestError(f"manifest missing required field: {key}")
    if not isinstance(data["name"], str) or not data["name"]:
        raise ManifestError("name must be a non-empty string")

    caps_raw = data.get("capabilities", [])
    if not isinstance(caps_raw, list):
        raise ManifestError("capabilities must be a list")
    caps = tuple(Capability.parse(c) for c in caps_raw)

    return PluginManifest(
        name=data["name"],
        version=str(data["version"]),
        entrypoint=str(data["entrypoint"]),
        plugin_object=str(data.get("plugin_object", "PLUGIN")),
        capabilities=caps,
        sha256=str(data["sha256"]).lower(),
        source_dir=plugin_dir,
    )


# ---------------------------------------------------------------------------
# Integrity
# ---------------------------------------------------------------------------


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_integrity(manifest: PluginManifest) -> str:
    """Hash the entry-point file and confirm it matches the manifest.

    Returns the actual digest.
    """
    if not manifest.entry_path.exists():
        raise IntegrityError(f"entrypoint not found: {manifest.entry_path}")
    actual = file_sha256(manifest.entry_path)
    if actual != manifest.sha256.lower():
        raise IntegrityError(
            f"sha256 mismatch for {manifest.name}: "
            f"manifest={manifest.sha256}, actual={actual}"
        )
    return actual


# ---------------------------------------------------------------------------
# Trust store
# ---------------------------------------------------------------------------


_DEFAULT_TRUST_DIR = Path.home() / ".opentama"
_DEFAULT_TRUST_PATH = _DEFAULT_TRUST_DIR / "trusted_plugins.json"


def get_trust_store_path() -> Path:
    env = os.environ.get("OPENTAMA_TRUST_STORE")
    return Path(env) if env else _DEFAULT_TRUST_PATH


@dataclass
class TrustStore:
    path: Path
    entries: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> "TrustStore":
        p = path or get_trust_store_path()
        if not p.exists():
            return cls(path=p, entries={})
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return cls(path=p, entries={})
        return cls(path=p, entries={str(k): str(v).lower() for k, v in data.items()})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self.entries, f, indent=2, sort_keys=True)
        tmp.replace(self.path)

    def is_trusted(self, manifest: PluginManifest) -> bool:
        return self.entries.get(manifest.trust_key, "") == manifest.sha256.lower()

    def trust(self, manifest: PluginManifest) -> None:
        self.entries[manifest.trust_key] = manifest.sha256.lower()
        self.save()

    def revoke(self, manifest_or_key: PluginManifest | str) -> bool:
        key = (
            manifest_or_key.trust_key
            if isinstance(manifest_or_key, PluginManifest)
            else manifest_or_key
        )
        if key in self.entries:
            del self.entries[key]
            self.save()
            return True
        return False


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


_DEFAULT_PLUGIN_DIR = Path.home() / ".opentama" / "plugins"


def get_plugin_dir() -> Path:
    env = os.environ.get("OPENTAMA_PLUGIN_DIR")
    return Path(env) if env else _DEFAULT_PLUGIN_DIR


@dataclass
class LoadedPlugin:
    manifest: PluginManifest
    instance: Plugin


class PluginLoader:
    """Locate, verify and instantiate plugins."""

    def __init__(
        self,
        plugin_dir: Path | None = None,
        trust_store: TrustStore | None = None,
    ):
        self.plugin_dir = plugin_dir or get_plugin_dir()
        self.trust_store = trust_store or TrustStore.load()

    # --- discovery --------------------------------------------------------

    def discover(self) -> list[PluginManifest]:
        if not self.plugin_dir.exists():
            return []
        manifests: list[PluginManifest] = []
        for child in sorted(self.plugin_dir.iterdir()):
            if not child.is_dir():
                continue
            try:
                manifests.append(parse_manifest(child))
            except ManifestError:
                continue
        return manifests

    # --- load -------------------------------------------------------------

    def load(self, manifest: PluginManifest, *, allow_untrusted: bool = False) -> LoadedPlugin:
        verify_integrity(manifest)
        if not allow_untrusted and not self.trust_store.is_trusted(manifest):
            raise NotTrustedError(
                f"plugin {manifest.trust_key} is not in the trust store "
                f"(sha256={manifest.sha256}). Trust it with the CLI before loading."
            )
        module = _import_module_from_path(manifest)
        if not hasattr(module, manifest.plugin_object):
            raise PluginError(
                f"plugin module is missing attribute {manifest.plugin_object!r}"
            )
        instance = getattr(module, manifest.plugin_object)
        if not isinstance(instance, Plugin):
            raise PluginError(
                f"{manifest.plugin_object} is not a Plugin instance"
            )
        if instance.name and instance.name != manifest.name:
            raise PluginError(
                f"plugin name mismatch: manifest={manifest.name!r} "
                f"instance={instance.name!r}"
            )
        return LoadedPlugin(manifest=manifest, instance=instance)

    def load_all(self, *, allow_untrusted: bool = False) -> list[LoadedPlugin]:
        return [self.load(m, allow_untrusted=allow_untrusted) for m in self.discover()]


def _import_module_from_path(manifest: PluginManifest):
    mod_name = f"opentama_plugin_{manifest.name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(mod_name, manifest.entry_path)
    if spec is None or spec.loader is None:
        raise PluginError(f"cannot create import spec for {manifest.entry_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception as e:  # noqa: BLE001
        del sys.modules[mod_name]
        raise PluginError(f"plugin import failed: {e}") from e
    return module


# ---------------------------------------------------------------------------
# Helpers used by the CLI
# ---------------------------------------------------------------------------


def make_context(
    capabilities: set[Capability],
    tama: Any = None,
    transport: Any = None,
) -> PluginContext:
    """Build a PluginContext for a loaded plugin.

    Only wires IR if the transport is present *and* IR capabilities are
    declared, so a display plugin never gets an IR send/recv pair even
    if a transport happens to be available.
    """
    ir_send = ir_recv = None
    if transport is not None and (
        Capability.IR_TRANSMIT in capabilities or Capability.IR_RECEIVE in capabilities
    ):
        ir_send = transport.send
        ir_recv = lambda t=1.0: transport.recv(timeout=t)
    return PluginContext(
        capabilities=set(capabilities),
        tama=tama,
        ir_send=ir_send,
        ir_recv=ir_recv,
    )
