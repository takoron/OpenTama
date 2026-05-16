"""Plugin subsystem for OpenTama."""

from .api import (
    Capability,
    CapabilityDenied,
    DisplayPlugin,
    Plugin,
    PluginContext,
    StateView,
)
from .loader import (
    IntegrityError,
    LoadedPlugin,
    ManifestError,
    NotTrustedError,
    PluginError,
    PluginLoader,
    PluginManifest,
    TrustStore,
    file_sha256,
    get_plugin_dir,
    get_trust_store_path,
    make_context,
    parse_manifest,
    verify_integrity,
)

__all__ = [
    "Capability",
    "CapabilityDenied",
    "DisplayPlugin",
    "IntegrityError",
    "LoadedPlugin",
    "ManifestError",
    "NotTrustedError",
    "Plugin",
    "PluginContext",
    "PluginError",
    "PluginLoader",
    "PluginManifest",
    "StateView",
    "TrustStore",
    "file_sha256",
    "get_plugin_dir",
    "get_trust_store_path",
    "make_context",
    "parse_manifest",
    "verify_integrity",
]
