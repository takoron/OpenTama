# Character credit — Takoron (タコロン)

OpenTama's pet is named **Takoron (タコロン)**. The character —
takoyaki ball with a bonito-flake hairpin, dot-eye smile, blushing
cheeks, and a peeking tongue — is an original creation, available
as a LINE sticker set:

  *タコロンばかり* (Takoron Bakari) — LINE store

The pixel sprites in `opentama/sprites.py` are an homage rendered in
monochrome at terminal resolution (14×16, drawn with Unicode
half-blocks ``▀ ▄ █``). They are deliberately small enough that they
could plausibly run on a real ガラケー LCD — not a faithful copy of
the LINE sticker artwork, which remains the artist's property.

## If you fork OpenTama and use your own pet

The sprite layer is intentionally decoupled. To swap Takoron for your
own pet:

1. Replace `opentama/sprites.py` with your own bitmap set (same
   stages: `egg`, `baby`, `child`, `teen`, `adult`, `elder`). The
   import-time width check will catch grid mistakes.
2. Update `CHARACTER.md` (this file) with your own credit.
3. Mention the change in `CHANGELOG.md`.

The growth engine, IR protocol, plugin system, and display backends
don't know or care which pet they're rendering — they just call into
`sprites.render(stage)`.

## Respecting the original

If you redistribute OpenTama with the bundled Takoron sprites
unchanged, please leave this credit file in place. The character
belongs to its creator; the surrounding software is MIT-licensed.
