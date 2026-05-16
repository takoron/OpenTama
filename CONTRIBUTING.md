# Contributing to OpenTama

Thanks for considering a contribution! OpenTama is meant to be small,
hackable, and fun to read. The bar for contributions is "another
person should still be able to understand the code three months from
now."

## Getting started

```bash
git clone <repo-url> opentama
cd opentama
pip install -e ".[dev]"
pytest                       # should print "152 passed" (or higher)
```

Python 3.11+ (we use stdlib `tomllib`). If you want to test against a
real USB IR adapter, also `pip install pyserial`.

## What we want

- Bug fixes with a regression test.
- New display backends (more ガラケー variants, e.g. PHS-style,
  early-smartphone, electronic dictionary…). Add a module under
  `opentama/displays/`, register it in `displays/__init__.py`, add at
  least one test.
- New stages, careful tweaks to growth/decay rates, new milestones —
  but please include numerical justification in the PR.
- Plugins (preferably as standalone repos that ship a `plugin.toml`).
- Internationalisation: messages are currently a mix of English,
  Japanese, and emoji. Translations welcome.

## What we don't want (without discussion first)

- Heavy dependencies. OpenTama deliberately depends only on the
  standard library at runtime (pyserial is optional, for real IR
  hardware).
- Networking. The pet's universe is the office WiFi + IR. We don't
  want a cloud backend.
- Breaking changes to the IR wire protocol without a version bump
  *and* a migration story.
- Anything that adds telemetry or "phone home" behaviour.

## Code style

- Black-compatible formatting (no formatter required, but match
  surrounding code).
- Type hints on new public APIs.
- Module-level docstrings explaining *why* the module exists, not
  just *what* it contains.
- Tests live in `tests/` and use the same style as existing ones.
- No new top-level dependencies without a discussion in an issue
  first.

## Plugin contributions

Built-in plugins live in `examples/plugins/`. They are documentation
as much as code — short, single-purpose, and explicit about which
capabilities they declare. Don't ship plugins that demonstrate one
capability but quietly use another.

When proposing a new built-in plugin:

1. Open an issue describing what it does and which capabilities it
   needs.
2. Land the manifest + entry file.
3. Recompute the sha256 with `python -m opentama plugin checksum
   examples/plugins/<your-plugin>/entry.py` and update the manifest in
   the same commit.

## Releasing

Maintainers only:

1. Update `CHANGELOG.md` (move `Unreleased` items into a new version
   section).
2. Bump `version` in `pyproject.toml` and `__version__` in
   `opentama/__init__.py`.
3. Tag: `git tag -s v0.X.0 -m "OpenTama 0.X.0"`.
4. `python -m build && twine upload dist/*` if publishing to PyPI.
5. Push the tag: `git push --tags`.

## Code of conduct

Be kind. Assume good faith. The pet is watching.
