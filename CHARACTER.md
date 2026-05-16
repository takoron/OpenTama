# Character credit — Takoron (タコロン)

OpenTama's pet is **Takoron (タコロン)** — a takoyaki ball with a
bonito-flake hairpin, dot-eye smile, blushing cheeks, and a peeking
tongue. The character is an original creation by the maintainer of
this project, also published as the LINE sticker set:

  *タコロンばかり２* — https://store.line.me/stickershop/product/1054531/ja

The pixel sprites in `opentama/sprites.py` are a deliberate
**low-resolution homage**: 14×16 monochrome bitmaps rendered with
Unicode half-blocks (`▀ ▄ █`), small enough to plausibly run on a real
ガラケー LCD. They are **not** a reproduction of the LINE sticker
artwork.

---

## Permission and scope

The character creator (the maintainer of this repository) grants the
following permissions, scoped to the pixel sprites bundled with
OpenTama and shipped from this repository:

1. **Internal use** within any organization that has cloned, forked,
   or installed OpenTama is permitted, including modifications to the
   surrounding software.

2. **Public redistribution of this repository unchanged** — including
   the bundled Takoron sprites — is permitted, provided this file
   (`CHARACTER.md`) is retained.

3. **Any other use of the Takoron name or likeness** — including
   merchandising, the LINE sticker artwork itself, derivative
   character art, or use in unrelated products — is **not** granted
   here and requires separate permission from the creator.

The software itself remains under the [MIT License](LICENSE). This
file governs only the bundled character artwork — the code is free to
reuse on its own under MIT.

---

## Forking with your own pet

The sprite layer is intentionally decoupled. To swap Takoron for a
different pet without touching any other code:

1. Replace `opentama/sprites.py` with your own bitmap set. Keep the
   same six stage keys: `egg`, `baby`, `child`, `teen`, `adult`,
   `elder`. The import-time width check will catch grid mistakes.
2. Rewrite this `CHARACTER.md` to credit your own character (and
   remove the Takoron permission grant above — it only applies to
   the sprites we ship, not to your replacement).
3. Note the swap in `CHANGELOG.md`.

The growth engine, IR protocol, plugin system, and display backends
don't know or care which pet they're rendering — they just call
`sprites.render(stage)`. A fork with your own pet is a one-file
diff.

---

## Reporting issues with the character art

If you spot a rendering bug, a width mismatch, or have a suggestion
for a new stage or facial expression, please open an issue using the
"Bug report" template and tag it with `character`. Pull requests that
adjust the sprite bitmaps are welcome — please keep the diff to
`opentama/sprites.py` and `tests/test_sprites.py`, and include
before/after rendered output in the PR description.
