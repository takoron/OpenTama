"""Tests for the plugin loader and trust store."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from opentama.plugins import (
    Capability,
    IntegrityError,
    ManifestError,
    NotTrustedError,
    PluginError,
    PluginLoader,
    TrustStore,
    parse_manifest,
    verify_integrity,
)


# --- helpers ----------------------------------------------------------------


SIMPLE_PLUGIN_CODE = '''\
from opentama.plugins import DisplayPlugin

class MyDisplay(DisplayPlugin):
    name = "my-display"
    version = "0.1.0"

    def render(self, view):
        return f"<{view.name}>"

PLUGIN = MyDisplay()
'''


IR_PLUGIN_CODE = '''\
from opentama.plugins import Plugin

class IRDemo(Plugin):
    name = "ir-demo"
    version = "0.1.0"

    def run(self, ctx):
        return list(ctx.capabilities)

PLUGIN = IRDemo()
'''


def _write_plugin(
    base: Path,
    name: str,
    version: str = "0.1.0",
    code: str = SIMPLE_PLUGIN_CODE,
    capabilities: list[str] | None = None,
    *,
    bad_sha: bool = False,
    extra_manifest: str = "",
) -> Path:
    plugin_dir = base / name
    plugin_dir.mkdir(parents=True)
    entry = plugin_dir / "entry.py"
    # If the canned code declares `name = "my-display"`, override it so
    # the instance matches the manifest. Skips files that opt out by
    # not having that exact string.
    rewritten = code.replace('name = "my-display"', f'name = "{name}"')
    entry.write_text(rewritten, encoding="utf-8")
    sha = hashlib.sha256(entry.read_bytes()).hexdigest()
    if bad_sha:
        sha = "0" * 64
    caps_line = ""
    if capabilities:
        caps_line = "capabilities = [" + ", ".join(f'"{c}"' for c in capabilities) + "]\n"
    manifest = (
        f'name = "{name}"\n'
        f'version = "{version}"\n'
        f'entrypoint = "entry"\n'
        f'plugin_object = "PLUGIN"\n'
        f'sha256 = "{sha}"\n'
        + caps_line
        + extra_manifest
    )
    (plugin_dir / "plugin.toml").write_text(manifest, encoding="utf-8")
    return plugin_dir


# --- manifest parsing -------------------------------------------------------


def test_parse_manifest_minimal(tmp_path: Path):
    d = _write_plugin(tmp_path, "tiny")
    m = parse_manifest(d)
    assert m.name == "tiny"
    assert m.entrypoint == "entry"
    assert m.plugin_object == "PLUGIN"
    assert len(m.sha256) == 64
    assert m.capabilities == ()


def test_parse_manifest_with_capabilities(tmp_path: Path):
    d = _write_plugin(tmp_path, "capz", capabilities=["display", "state.read"])
    m = parse_manifest(d)
    assert Capability.DISPLAY in m.capabilities
    assert Capability.STATE_READ in m.capabilities


def test_parse_manifest_unknown_capability_rejected(tmp_path: Path):
    d = _write_plugin(tmp_path, "bad-cap", capabilities=["nuclear.launch"])
    with pytest.raises(ValueError):
        parse_manifest(d)


def test_parse_manifest_missing_field_rejected(tmp_path: Path):
    d = tmp_path / "incomplete"
    d.mkdir()
    (d / "plugin.toml").write_text('name = "x"\nversion = "1"\n', encoding="utf-8")
    with pytest.raises(ManifestError):
        parse_manifest(d)


def test_parse_manifest_missing_file(tmp_path: Path):
    with pytest.raises(ManifestError):
        parse_manifest(tmp_path / "ghost")


# --- integrity --------------------------------------------------------------


def test_verify_integrity_passes_when_hash_matches(tmp_path: Path):
    d = _write_plugin(tmp_path, "ok")
    m = parse_manifest(d)
    assert verify_integrity(m) == m.sha256


def test_verify_integrity_detects_tampering(tmp_path: Path):
    d = _write_plugin(tmp_path, "tamper")
    m = parse_manifest(d)
    # Modify the entry-point file after manifest is written.
    (d / "entry.py").write_text(SIMPLE_PLUGIN_CODE + "# tampered\n", encoding="utf-8")
    with pytest.raises(IntegrityError):
        verify_integrity(m)


def test_verify_integrity_rejects_wrong_declared_hash(tmp_path: Path):
    d = _write_plugin(tmp_path, "wrong-sha", bad_sha=True)
    m = parse_manifest(d)
    with pytest.raises(IntegrityError):
        verify_integrity(m)


# --- trust store ------------------------------------------------------------


def test_trust_store_save_load(tmp_path: Path):
    path = tmp_path / "trust.json"
    store = TrustStore(path=path)
    d = _write_plugin(tmp_path, "trusted-one")
    m = parse_manifest(d)
    store.trust(m)
    assert path.exists()
    loaded = TrustStore.load(path)
    assert loaded.is_trusted(m)


def test_trust_store_revoke(tmp_path: Path):
    path = tmp_path / "trust.json"
    store = TrustStore(path=path)
    d = _write_plugin(tmp_path, "revokable")
    m = parse_manifest(d)
    store.trust(m)
    assert store.revoke(m) is True
    assert store.revoke(m) is False  # second revoke is a no-op
    assert not TrustStore.load(path).is_trusted(m)


def test_trust_is_version_specific(tmp_path: Path):
    path = tmp_path / "trust.json"
    store = TrustStore(path=path)
    d1 = _write_plugin(tmp_path / "v1", "samename", version="1.0.0")
    d2 = _write_plugin(tmp_path / "v2", "samename", version="2.0.0")
    m1 = parse_manifest(d1)
    m2 = parse_manifest(d2)
    store.trust(m1)
    assert store.is_trusted(m1)
    assert not store.is_trusted(m2)


def test_trust_is_sha_specific(tmp_path: Path):
    """Trusting the manifest pins its hash too."""
    path = tmp_path / "trust.json"
    store = TrustStore(path=path)
    d = _write_plugin(tmp_path, "pinned")
    m = parse_manifest(d)
    store.trust(m)
    # Rewrite the trust file with a different hash, but the same key.
    path.write_text(json.dumps({m.trust_key: "deadbeef" * 8}), encoding="utf-8")
    store2 = TrustStore.load(path)
    assert not store2.is_trusted(m)


# --- loader -----------------------------------------------------------------


def test_loader_discovers_plugins(tmp_path: Path):
    _write_plugin(tmp_path, "alpha")
    _write_plugin(tmp_path, "beta")
    loader = PluginLoader(plugin_dir=tmp_path, trust_store=TrustStore(path=tmp_path / "t.json"))
    found = {m.name for m in loader.discover()}
    assert found == {"alpha", "beta"}


def test_loader_refuses_untrusted_by_default(tmp_path: Path):
    _write_plugin(tmp_path, "shifty")
    loader = PluginLoader(plugin_dir=tmp_path, trust_store=TrustStore(path=tmp_path / "t.json"))
    [manifest] = loader.discover()
    with pytest.raises(NotTrustedError):
        loader.load(manifest)


def test_loader_allows_untrusted_when_explicit(tmp_path: Path):
    _write_plugin(tmp_path, "explicit")
    loader = PluginLoader(plugin_dir=tmp_path, trust_store=TrustStore(path=tmp_path / "t.json"))
    [manifest] = loader.discover()
    loaded = loader.load(manifest, allow_untrusted=True)
    assert loaded.instance.name == "explicit"


def test_loader_loads_after_trusting(tmp_path: Path):
    _write_plugin(tmp_path, "blessed")
    ts = TrustStore(path=tmp_path / "t.json")
    loader = PluginLoader(plugin_dir=tmp_path, trust_store=ts)
    [manifest] = loader.discover()
    ts.trust(manifest)
    loaded = loader.load(manifest)
    assert loaded.manifest.name == "blessed"


def test_loader_rejects_when_name_mismatches_instance(tmp_path: Path):
    # Hand-craft code whose declared name doesn't match the manifest.
    code = SIMPLE_PLUGIN_CODE.replace('name = "my-display"', 'name = "different"')
    plugin_dir = tmp_path / "namemix"
    plugin_dir.mkdir()
    (plugin_dir / "entry.py").write_text(code, encoding="utf-8")
    sha = hashlib.sha256((plugin_dir / "entry.py").read_bytes()).hexdigest()
    (plugin_dir / "plugin.toml").write_text(
        f'name = "namemix"\nversion = "0.1.0"\n'
        f'entrypoint = "entry"\nplugin_object = "PLUGIN"\n'
        f'sha256 = "{sha}"\n',
        encoding="utf-8",
    )
    loader = PluginLoader(plugin_dir=tmp_path, trust_store=TrustStore(path=tmp_path / "t.json"))
    [manifest] = loader.discover()
    with pytest.raises(PluginError):
        loader.load(manifest, allow_untrusted=True)


def test_loader_rejects_missing_plugin_attr(tmp_path: Path):
    _write_plugin(tmp_path, "no-attr", code="X = 1\n")
    loader = PluginLoader(plugin_dir=tmp_path, trust_store=TrustStore(path=tmp_path / "t.json"))
    [manifest] = loader.discover()
    with pytest.raises(PluginError):
        loader.load(manifest, allow_untrusted=True)


def test_loader_discover_handles_empty_dir(tmp_path: Path):
    loader = PluginLoader(plugin_dir=tmp_path / "ghost", trust_store=TrustStore(path=tmp_path / "t.json"))
    assert loader.discover() == []
